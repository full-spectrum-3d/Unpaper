"""Konwerter LibreOffice uruchamiany jako osobny proces (spec §3.4, §5.2, §10.2).

Moduł uruchamia niezmodyfikowane binarium `soffice` bez powłoki, ze stałymi argumentami.
Każde wywołanie dostaje własny katalog roboczy z profilem użytkownika, więc równoległe
konwersje się nie blokują.

Przy timeoucie albo anulowaniu zabijamy całą grupę procesów: na Alpine `soffice` to
skrypt, który uruchamia `oosplash`, a ten `soffice.bin`. Samo `kill` dziecka zostawiłoby
działający `soffice.bin`.
"""

import asyncio
import contextlib
import logging
import os
import shutil
import signal
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import Request

from app.core.config import Settings
from app.pipeline.upload_validation.policy import FileKind

logger = logging.getLogger(__name__)

STDERR_TAIL_BYTES = 2048

_FILTERS = {
    FileKind.DOCX: "docx:MS Word 2007 XML",
    FileKind.XLSX: "xlsx:Calc MS Excel 2007 XML",
}

# Profil zasiewany w każdym katalogu roboczym. LibreOffice headless nie uruchamia makr przy
# konwersji; blokada makr to drugi bezpiecznik. Aktualizacja łączy wyłączona (0 = nigdy):
# pola INCLUDETEXT/INCLUDEPICTURE, sekcje i arkusze połączone z dokumentu niezaufanego mogłyby
# inaczej wczytać do wyniku lokalne pliki (np. /proc/self/environ).
_MACRO_LOCKDOWN_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>
</oor:items>
"""  # noqa: E501


class ConversionError(Exception):
    """Konwersja się nie udała (kod wyjścia, brak wyniku, błąd uruchomienia)."""


class ConverterTimeoutError(ConversionError):
    """Konwersja przekroczyła `CONVERTER_TIMEOUT_S`."""


@dataclass(frozen=True, slots=True)
class RunResult:
    returncode: int
    stderr_tail: bytes


class Runner(Protocol):
    async def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        timeout_s: float,
    ) -> RunResult: ...


_HAS_KILLPG = hasattr(os, "killpg")


def _kill(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        if _HAS_KILLPG:
            os.killpg(proc.pid, signal.SIGKILL)  # type: ignore[attr-defined,unused-ignore]
        else:
            proc.kill()


async def run_process(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path,
    timeout_s: float,
) -> RunResult:
    """Uruchamia proces we własnej grupie; po timeoucie lub anulowaniu zabija całą grupę."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=dict(env),
        start_new_session=_HAS_KILLPG,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout_s)
    except TimeoutError as exc:
        _kill(proc)
        await proc.wait()
        raise ConverterTimeoutError(f"przekroczono {timeout_s} s") from exc
    except BaseException:
        _kill(proc)
        await asyncio.shield(proc.wait())
        raise
    assert proc.returncode is not None  # noqa: S101 - communicate() czeka na zakończenie
    return RunResult(proc.returncode, stderr[-STDERR_TAIL_BYTES:])


class Converter(Protocol):
    async def convert(self, source: Path, target: FileKind, workdir: Path) -> Path:
        """Konwertuje `source` do `target` w `workdir`; zwraca ścieżkę niepustego wyniku."""
        ...


class LibreOfficeConverter:
    """`soffice --headless --convert-to` z osobnym profilem w katalogu roboczym."""

    def __init__(self, soffice_path: str, timeout_s: float, runner: Runner = run_process) -> None:
        self.soffice_path = soffice_path
        self.timeout_s = timeout_s
        self._runner = runner

    async def convert(self, source: Path, target: FileKind, workdir: Path) -> Path:
        if target not in _FILTERS:
            raise ValueError(f"nieobsługiwany format docelowy: {target}")
        profile = workdir / "profile"
        outdir = workdir / "out"
        (profile / "user").mkdir(parents=True)
        outdir.mkdir()
        (profile / "user" / "registrymodifications.xcu").write_text(
            _MACRO_LOCKDOWN_XCU, encoding="utf-8"
        )
        argv = [
            self.soffice_path,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--invisible",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--nologo",
            "--convert-to",
            _FILTERS[target],
            "--outdir",
            str(outdir),
            str(source),
        ]
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(workdir),
            "TMPDIR": str(workdir),
            "LANG": "C.UTF-8",
        }
        started = time.monotonic()
        try:
            result = await self._runner(argv, env=env, cwd=workdir, timeout_s=self.timeout_s)
        except OSError as exc:
            logger.warning("nie udało się uruchomić konwertera: %s", type(exc).__name__)
            raise ConversionError("nie udało się uruchomić konwertera") from exc
        elapsed = time.monotonic() - started

        output = outdir / f"{source.stem}.{target}"
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            logger.debug(
                "konwersja nieudana: kod %s, stderr: %r", result.returncode, result.stderr_tail
            )
            raise ConversionError(f"brak wyniku konwersji (kod wyjścia {result.returncode})")
        logger.info("konwersja do %s: %.1f s, %d B", target, elapsed, output.stat().st_size)
        return output


def find_converter(settings: Settings) -> LibreOfficeConverter | None:
    """Konwerter, gdy `soffice` jest w obrazie; `None` = Plan B (DOC/ODS → 415)."""
    path = shutil.which("soffice") or shutil.which("libreoffice")
    if path is None:
        return None
    return LibreOfficeConverter(path, settings.converter_timeout_s)


def get_converter(request: Request) -> Converter | None:
    """Zależność FastAPI: konwerter wykryty przy starcie aplikacji."""
    converter: Converter | None = request.app.state.converter
    return converter
