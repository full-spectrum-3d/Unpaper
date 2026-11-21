"""Orkiestracja walidacji uploadu w kolejności z §6.3.

Dwa wejścia:
- `accept_upload` - strumień żądania HTTP → zwalidowany plik (pkt 1-9). Nazwę i rozszerzenie
  sprawdzamy z nagłówka części, zanim przeczytamy treść, żeby nie przyjmować np. 20 MB
  pliku .exe tylko po to, żeby go odrzucić,
- `validate_file` - plik już otwarty (skrypt batch, inne źródło) → pkt 2-9.

Plik zabezpieczony hasłem odszyfrowujemy zaraz po wykryciu MIME (moduł `encryption`), a
wszystkie dalsze sprawdzenia wykonujemy na jawnej treści. `ValidatedUpload.file` wskazuje
wtedy odszyfrowaną kopię, a oryginał można zamknąć.
"""

from collections.abc import AsyncIterable
from dataclasses import dataclass
from types import TracebackType
from typing import IO, Self

import anyio.to_thread

from app.pipeline.upload_validation.containers import inspect_doc, inspect_zip_document
from app.pipeline.upload_validation.documents import inspect_image, inspect_pdf
from app.pipeline.upload_validation.encryption import unlock_if_protected
from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.filename import check_filename, normalize_filename, resolve_kind
from app.pipeline.upload_validation.mime import check_mime, detect_mime
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from app.pipeline.upload_validation.receive import receive_single_file


@dataclass(slots=True)
class ValidatedUpload:
    """Plik po walidacji. Strumień `file` jest ustawiony na początek.

    Właściciel zamyka go po zakończeniu żądania (`close()` albo `with`). Zamknięcie zwalnia
    pamięć albo usuwa anonimowy plik tymczasowy (spec §10.3).
    """

    filename: str
    extension: str
    kind: FileKind
    mime: str
    size_bytes: int
    file: IO[bytes]
    page_count: int | None = None
    """PDF: liczba stron."""
    image_size: tuple[int, int] | None = None
    """JPEG/PNG: (szerokość, wysokość) w pikselach."""
    decrypted: bool = False
    """Plik był zabezpieczony hasłem; `file` i `mime` dotyczą odszyfrowanej treści."""

    def close(self) -> None:
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


def _checked_filename(raw: str) -> str:
    name = normalize_filename(raw)
    check_filename(name)
    resolve_kind(name)
    return name


async def accept_upload(
    chunks: AsyncIterable[bytes],
    content_type: str | None,
    limits: UploadLimits,
    *,
    tmp_dir: str | None = None,
) -> ValidatedUpload:
    """Odbiera jedyny plik z pola `file` żądania multipart i waliduje go w całości.

    `chunks` to np. `request.stream()` ze Starlette. Opcjonalne pole `password` w tym samym
    żądaniu odblokowuje dokument z hasłem. Sprawdzenia zawartości (libmagic, ZIP, PDFium,
    Pillow, KDF) blokują, więc wykonujemy je w puli wątków.
    """
    received = await receive_single_file(
        chunks,
        content_type,
        max_file_bytes=limits.max_file_bytes,
        spool_max_bytes=limits.spool_max_bytes,
        check_filename=_checked_filename,
        tmp_dir=tmp_dir,
    )
    try:
        upload = await anyio.to_thread.run_sync(
            lambda: validate_file(
                received.filename,
                received.file,
                limits,
                password=received.password,
                tmp_dir=tmp_dir,
            )
        )
    except BaseException:
        received.close()
        raise
    if upload.file is not received.file:
        received.close()  # zostaje tylko odszyfrowana kopia
    return upload


def validate_file(
    filename: str,
    file: IO[bytes],
    limits: UploadLimits,
    *,
    password: str | None = None,
    tmp_dir: str | None = None,
) -> ValidatedUpload:
    """Waliduje otwarty, przewijalny plik (pkt 2-9). Nie zamyka `file`.

    Gdy plik był zaszyfrowany, wynik zawiera nowy strumień z odszyfrowaną treścią, a `file`
    pozostaje własnością wołającego.
    """
    name = normalize_filename(filename)
    check_filename(name)
    extension, kind = resolve_kind(name)
    size = _measure(file, limits)

    detected = detect_mime(file)
    unlocked = unlock_if_protected(file, kind, detected, password, limits, tmp_dir=tmp_dir)
    if unlocked is None:
        return _inspect(name, extension, kind, size, detected, file, limits, decrypted=False)
    try:
        return _inspect(
            name, extension, kind, size, detect_mime(unlocked), unlocked, limits, decrypted=True
        )
    except BaseException:
        unlocked.close()
        raise


def _inspect(
    name: str,
    extension: str,
    kind: FileKind,
    size: int,
    detected: str,
    file: IO[bytes],
    limits: UploadLimits,
    *,
    decrypted: bool,
) -> ValidatedUpload:
    """Pkt 6-9 na (ewentualnie odszyfrowanej) treści."""
    check_mime(kind, extension, detected)

    page_count: int | None = None
    image_size: tuple[int, int] | None = None
    match kind:
        case FileKind.PDF:
            page_count = inspect_pdf(file, limits)
        case FileKind.DOC:
            inspect_doc(file)
        case FileKind.DOCX | FileKind.XLSX | FileKind.ODS:
            inspect_zip_document(file, kind, limits)
        case FileKind.JPEG | FileKind.PNG:
            image_size = inspect_image(file, kind, limits)

    file.seek(0)
    return ValidatedUpload(
        filename=name,
        extension=extension,
        kind=kind,
        mime=detected,
        size_bytes=size,
        file=file,
        page_count=page_count,
        image_size=image_size,
        decrypted=decrypted,
    )


def _measure(file: IO[bytes], limits: UploadLimits) -> int:
    size = file.seek(0, 2)
    file.seek(0)
    if size > limits.max_file_bytes:
        raise UploadError(
            UploadErrorCode.FILE_TOO_LARGE,
            f"Plik ma {size} B, limit to {limits.max_file_bytes} B",
        )
    if size == 0:
        raise UploadError(UploadErrorCode.FILE_EMPTY, "Przesłany plik ma 0 bajtów")
    return size
