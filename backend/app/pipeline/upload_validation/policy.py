"""Reguły uploadu: limity, obsługiwane formaty i akceptowane MIME (spec §6.3, §12).

Wartości domyślne odpowiadają tabeli konfiguracji ze specyfikacji. `UploadLimits`
budujemy w warstwie API z ustawień aplikacji (`MAX_FILE_SIZE_MB` itd.).
"""

from dataclasses import dataclass
from enum import StrEnum

MIB = 1024 * 1024

MAX_FILENAME_LENGTH = 250
FORBIDDEN_FILENAME_CHARS = frozenset(";:><\\/|'*%$")
FILE_FIELD_NAME = "file"
PASSWORD_FIELD_NAME = "password"  # noqa: S105 - nazwa, nie hasło
MAX_PASSWORD_BYTES = 1024
"""Office przyjmuje do 255 znaków, PDF i ODF mniej lub tyle samo; 1 KB to bezpieczny zapas."""


@dataclass(frozen=True, slots=True)
class UploadLimits:
    max_file_bytes: int = 20 * MIB
    """MAX_FILE_SIZE_MB: maksymalny rozmiar pliku (wymóg M4)."""
    spool_max_bytes: int = 10 * MIB
    """SPOOL_MAX_MB: do tego progu plik jest w RAM, powyżej trafia na tmpfs."""
    max_uncompressed_bytes: int = 100 * MIB
    """MAX_UNCOMPRESSED_MB: suma rozmiarów wpisów DOCX/XLSX/ODS po dekompresji."""
    max_archive_entries: int = 10_000
    """Maksymalna liczba wpisów w kontenerze ZIP."""
    max_pdf_pages: int = 30
    """MAX_PDF_PAGES."""
    max_image_pixels: int = 100_000_000
    """MAX_IMAGE_PIXELS."""

    @classmethod
    def from_megabytes(
        cls,
        *,
        max_file_size_mb: float,
        spool_max_mb: float,
        max_uncompressed_mb: float,
        max_pdf_pages: int,
        max_image_pixels: int,
        max_archive_entries: int = 10_000,
    ) -> UploadLimits:
        return cls(
            max_file_bytes=int(max_file_size_mb * MIB),
            spool_max_bytes=int(spool_max_mb * MIB),
            max_uncompressed_bytes=int(max_uncompressed_mb * MIB),
            max_archive_entries=max_archive_entries,
            max_pdf_pages=max_pdf_pages,
            max_image_pixels=max_image_pixels,
        )


class FileKind(StrEnum):
    """Rodzaj dokumentu wyznaczony z rozszerzenia i potwierdzony zawartością."""

    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    XLSX = "xlsx"
    ODS = "ods"
    JPEG = "jpeg"
    PNG = "png"


EXTENSION_KINDS: dict[str, FileKind] = {
    "pdf": FileKind.PDF,
    "doc": FileKind.DOC,
    "docx": FileKind.DOCX,
    "xlsx": FileKind.XLSX,
    "ods": FileKind.ODS,
    "jpg": FileKind.JPEG,
    "jpeg": FileKind.JPEG,
    "png": FileKind.PNG,
}

MIME_ZIP = "application/zip"
MIME_OLE_GENERIC = frozenset({"application/x-ole-storage", "application/CDFV2"})

ACCEPTED_MIME: dict[FileKind, frozenset[str]] = {
    FileKind.PDF: frozenset({"application/pdf"}),
    FileKind.DOC: frozenset({"application/msword"}) | MIME_OLE_GENERIC,
    FileKind.DOCX: frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", MIME_ZIP}
    ),
    FileKind.XLSX: frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", MIME_ZIP}
    ),
    FileKind.ODS: frozenset({"application/vnd.oasis.opendocument.spreadsheet", MIME_ZIP}),
    FileKind.JPEG: frozenset({"image/jpeg"}),
    FileKind.PNG: frozenset({"image/png"}),
}

ZIP_KINDS = frozenset({FileKind.DOCX, FileKind.XLSX, FileKind.ODS})
