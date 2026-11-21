"""Błędy walidacji uploadu (spec §6.3, §6.4).

Każdy błąd niesie kod, status HTTP i tytuł. Warstwa API zamienia je na
`application/problem+json` (RFC 9457). Treść `detail` nie zawiera danych z pliku,
najwyżej nazwę pliku albo znak, który ją dyskwalifikuje, i nigdy nie zawiera hasła.

`DOCUMENT_PASSWORD_REQUIRED` i `DOCUMENT_PASSWORD_INVALID` to sygnał dla frontendu, żeby
poprosił o hasło i ponowił żądanie z polem `password`.
"""

from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus


class UploadErrorCode(StrEnum):
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    FILE_MISSING = "FILE_MISSING"
    TOO_MANY_FILES = "TOO_MANY_FILES"
    FILENAME_TOO_LONG = "FILENAME_TOO_LONG"
    FILENAME_FORBIDDEN_CHARS = "FILENAME_FORBIDDEN_CHARS"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_EMPTY = "FILE_EMPTY"
    UNSUPPORTED_EXTENSION = "UNSUPPORTED_EXTENSION"
    MIME_MISMATCH = "MIME_MISMATCH"
    ARCHIVE_TOO_LARGE = "ARCHIVE_TOO_LARGE"
    DOCUMENT_TOO_COMPLEX = "DOCUMENT_TOO_COMPLEX"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    DOCUMENT_PASSWORD_REQUIRED = "DOCUMENT_PASSWORD_REQUIRED"  # noqa: S105 - nazwa, nie hasło
    DOCUMENT_PASSWORD_INVALID = "DOCUMENT_PASSWORD_INVALID"  # noqa: S105 - nazwa, nie hasło


@dataclass(frozen=True, slots=True)
class _ErrorSpec:
    status: HTTPStatus
    title: str


_SPECS: dict[UploadErrorCode, _ErrorSpec] = {
    UploadErrorCode.MALFORMED_REQUEST: _ErrorSpec(
        HTTPStatus.BAD_REQUEST, "Niepoprawne żądanie multipart/form-data"
    ),
    UploadErrorCode.FILE_MISSING: _ErrorSpec(HTTPStatus.BAD_REQUEST, "Brak pliku w żądaniu"),
    UploadErrorCode.TOO_MANY_FILES: _ErrorSpec(
        HTTPStatus.BAD_REQUEST, "Żądanie może zawierać tylko jeden plik"
    ),
    UploadErrorCode.FILENAME_TOO_LONG: _ErrorSpec(
        HTTPStatus.BAD_REQUEST, "Nazwa pliku jest za długa"
    ),
    UploadErrorCode.FILENAME_FORBIDDEN_CHARS: _ErrorSpec(
        HTTPStatus.BAD_REQUEST, "Niedozwolone znaki w nazwie pliku"
    ),
    UploadErrorCode.FILE_TOO_LARGE: _ErrorSpec(
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Plik jest za duży"
    ),
    UploadErrorCode.FILE_EMPTY: _ErrorSpec(HTTPStatus.BAD_REQUEST, "Plik jest pusty"),
    UploadErrorCode.UNSUPPORTED_EXTENSION: _ErrorSpec(
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Nieobsługiwany format pliku"
    ),
    UploadErrorCode.MIME_MISMATCH: _ErrorSpec(
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Zawartość pliku nie pasuje do rozszerzenia"
    ),
    UploadErrorCode.ARCHIVE_TOO_LARGE: _ErrorSpec(
        HTTPStatus.UNPROCESSABLE_CONTENT, "Dokument po rozpakowaniu jest za duży"
    ),
    UploadErrorCode.DOCUMENT_TOO_COMPLEX: _ErrorSpec(
        HTTPStatus.UNPROCESSABLE_CONTENT, "Dokument jest zbyt złożony"
    ),
    UploadErrorCode.DOCUMENT_UNREADABLE: _ErrorSpec(
        HTTPStatus.UNPROCESSABLE_CONTENT, "Nie można odczytać dokumentu"
    ),
    UploadErrorCode.DOCUMENT_PASSWORD_REQUIRED: _ErrorSpec(
        HTTPStatus.UNPROCESSABLE_CONTENT, "Dokument jest zabezpieczony hasłem"
    ),
    UploadErrorCode.DOCUMENT_PASSWORD_INVALID: _ErrorSpec(
        HTTPStatus.UNPROCESSABLE_CONTENT, "Niepoprawne hasło do dokumentu"
    ),
}


class UploadError(Exception):
    """Odrzucenie pliku na etapie [1] pipeline'u."""

    def __init__(self, code: UploadErrorCode, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    @property
    def status(self) -> HTTPStatus:
        return _SPECS[self.code].status

    @property
    def title(self) -> str:
        return _SPECS[self.code].title
