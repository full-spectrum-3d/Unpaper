"""Walidacja nazwy pliku i rozszerzenia (spec §6.3, pkt 2, 3, 5).

Nazwa od klienta służy tylko do raportu i rozpoznania rozszerzenia. Nigdy nie
trafia do ścieżki w systemie plików.
"""

import unicodedata

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import (
    EXTENSION_KINDS,
    FORBIDDEN_FILENAME_CHARS,
    MAX_FILENAME_LENGTH,
    FileKind,
)


def normalize_filename(raw: str) -> str:
    """NFC, żeby „ą” zapisane jako dwa punkty kodowe liczyło się jako jeden znak."""
    return unicodedata.normalize("NFC", raw)


def check_filename(name: str) -> None:
    """Pkt 2 i 3: długość ≤ 250 znaków, bez `; : > < / \\ | ' * % $` i znaków sterujących."""
    if len(name) > MAX_FILENAME_LENGTH:
        raise UploadError(
            UploadErrorCode.FILENAME_TOO_LONG,
            f"Nazwa pliku ma {len(name)} znaków, dopuszczalne jest {MAX_FILENAME_LENGTH}",
        )
    for char in name:
        if char in FORBIDDEN_FILENAME_CHARS:
            raise UploadError(
                UploadErrorCode.FILENAME_FORBIDDEN_CHARS,
                f"Nazwa pliku zawiera znak '{char}'",
            )
        if unicodedata.category(char) == "Cc":
            raise UploadError(
                UploadErrorCode.FILENAME_FORBIDDEN_CHARS,
                f"Nazwa pliku zawiera znak sterujący U+{ord(char):04X}",
            )


def resolve_kind(name: str) -> tuple[str, FileKind]:
    """Pkt 5: rozszerzenie bez rozróżniania wielkości liter → (rozszerzenie, rodzaj)."""
    stem, dot, extension = name.rpartition(".")
    extension = extension.lower()
    allowed = ", ".join(f".{ext}" for ext in EXTENSION_KINDS)
    if not dot or not extension:
        problem = "Plik nie ma rozszerzenia"
    elif not stem.strip():
        problem = "Nazwa pliku nie może składać się z samego rozszerzenia"
    elif extension not in EXTENSION_KINDS:
        problem = f"Rozszerzenie .{extension} nie jest obsługiwane"
    else:
        return extension, EXTENSION_KINDS[extension]
    raise UploadError(UploadErrorCode.UNSUPPORTED_EXTENSION, f"{problem}. Dozwolone: {allowed}")
