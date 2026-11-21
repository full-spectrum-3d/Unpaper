"""Wykrywanie MIME z zawartości (libmagic) i porównanie z rozszerzeniem (spec §6.3 pkt 6).

Nagłówek `Content-Type` części multipart ignorujemy, bo kontroluje go klient.
"""

from typing import IO

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import ACCEPTED_MIME, MIME_ZIP, FileKind

MAGIC_BUFFER_BYTES = 1024 * 1024
"""Tyle czyta libmagic domyślnie (bytes_max). Wystarcza też do rozpoznania OOXML/ODS."""

_MIME_UNKNOWN = "application/octet-stream"
_ZIP_LOCAL_HEADER = b"PK\x03\x04"


def detect_mime(file: IO[bytes]) -> str:
    # Import leniwy: brak libmagic (np. Windows bez DLL) nie blokuje importu pakietu.
    import magic

    file.seek(0)
    head = file.read(MAGIC_BUFFER_BYTES)
    file.seek(0)
    detected = str(magic.from_buffer(head, mime=True))
    # libmagic w trybie bufora nie rozpoznaje ogólnego ZIP-a (zwraca "data"), choć z pliku
    # rozpoznaje. Bez tego np. ODS ze skompresowanym wpisem `mimetype` nie dotarłby do
    # sprawdzenia struktury (spec §6.3: "application/zip + pkt 7").
    if detected == _MIME_UNKNOWN and head.startswith(_ZIP_LOCAL_HEADER):
        return MIME_ZIP
    return detected


def check_mime(kind: FileKind, extension: str, detected: str) -> None:
    if detected not in ACCEPTED_MIME[kind]:
        raise UploadError(
            UploadErrorCode.MIME_MISMATCH,
            f"Plik z rozszerzeniem .{extension} ma zawartość typu {detected}",
        )
