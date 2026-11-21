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
import os
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

STDERR_TAIL_BYTES = 2048


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
