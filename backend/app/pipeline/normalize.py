"""[2] Normalizacja: DOC→DOCX, ODS→XLSX przez LibreOffice headless (spec §5.2).

Pozostałe formaty przechodzą bez zmian i bez kopiowania. Konwersja odbywa się w osobnym
`TemporaryDirectory` na wywołanie; wynik wczytujemy do `SpooledTemporaryFile`, a katalog
usuwamy od razu, także przy błędzie, timeoucie i anulowaniu (spec §10.3). Wynik
LibreOffice to nadal dane niezaufane, więc przechodzi tę samą kontrolę ZIP co upload.
"""

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import IO, Self

import anyio.to_thread

from app.core.errors import AppError, ErrorCode
from app.pipeline.converter import ConversionError, Converter, ConverterTimeoutError
from app.pipeline.upload_validation.containers import inspect_zip_document
from app.pipeline.upload_validation.errors import UploadError
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from app.pipeline.upload_validation.validate import ValidatedUpload

_TARGETS: dict[FileKind, tuple[FileKind, str]] = {
    FileKind.DOC: (FileKind.DOCX, "doc"),
    FileKind.ODS: (FileKind.XLSX, "ods"),
}


@dataclass(slots=True)
class NormalizedDocument:
    """Dokument w formacie obsługiwanym przez ekstraktory. `file` jest na początku."""

    kind: FileKind
    """PDF, DOCX, XLSX, JPEG albo PNG - nigdy DOC/ODS."""
    file: IO[bytes]
    converted: bool
    """True: `file` to nowy strumień należący do tego obiektu. False: to `upload.file`."""

    def close(self) -> None:
        """Zamyka tylko własny strumień; `upload.file` zamyka właściciel uploadu."""
        if self.converted:
            self.file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


async def normalize(
    upload: ValidatedUpload,
    converter: Converter | None,
    limits: UploadLimits,
    *,
    tmp_dir: str | None = None,
) -> NormalizedDocument:
    """Przekazuje dokument dalej albo konwertuje DOC/ODS (spec §5.2, Plan B z §3.4)."""
    if upload.kind not in _TARGETS:
        upload.file.seek(0)
        return NormalizedDocument(upload.kind, upload.file, converted=False)
    target, ext = _TARGETS[upload.kind]
    if converter is None:
        raise AppError(
            ErrorCode.UNSUPPORTED_EXTENSION,
            f"Format .{ext} wymaga LibreOffice, który nie jest dostępny w tej instalacji",
        )

    with tempfile.TemporaryDirectory(prefix="coi-conv-", dir=tmp_dir) as workdir_name:
        workdir = Path(workdir_name)
        source = workdir / "in" / f"input.{ext}"
        await anyio.to_thread.run_sync(_write_input, upload.file, source)
        try:
            output = await converter.convert(source, target, workdir)
            spool = await anyio.to_thread.run_sync(_load_output, output, target, limits, tmp_dir)
        except ConverterTimeoutError as exc:
            raise AppError(ErrorCode.PROCESSING_TIMEOUT, "Przekroczono czas konwersji") from exc
        except (ConversionError, UploadError) as exc:
            raise AppError(
                ErrorCode.DOCUMENT_UNREADABLE, f"Nie udało się przekonwertować pliku .{ext}"
            ) from exc
    return NormalizedDocument(target, spool, converted=True)


def _write_input(file: IO[bytes], source: Path) -> None:
    source.parent.mkdir()
    file.seek(0)
    try:
        with source.open("wb") as handle:
            shutil.copyfileobj(file, handle)
    finally:
        file.seek(0)


def _load_output(
    output: Path, target: FileKind, limits: UploadLimits, tmp_dir: str | None
) -> IO[bytes]:
    # Własność strumienia przechodzi na NormalizedDocument, więc bez `with`.
    spool: IO[bytes] = tempfile.SpooledTemporaryFile(  # noqa: SIM115
        max_size=limits.spool_max_bytes, dir=tmp_dir
    )
    try:
        with output.open("rb") as handle:
            shutil.copyfileobj(handle, spool)
        inspect_zip_document(spool, target, limits)
        spool.seek(0)
    except BaseException:
        spool.close()
        raise
    return spool
