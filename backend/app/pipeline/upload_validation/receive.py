"""Strumieniowy odbiór żądania multipart/form-data z jednym plikiem (spec §6.3 pkt 1-5, §10.3).

Parsujemy surowy strumień żądania samodzielnie, zamiast polegać na `UploadFile`.
Dzięki temu:
- nazwę i rozszerzenie sprawdzamy z nagłówka części, zanim przeczytamy jej treść,
- rozmiar liczymy w trakcie odbioru i przerywamy po przekroczeniu limitu,
- drugi plik w żądaniu przerywa odbiór od razu,
- opcjonalne pole tekstowe `password` (hasło do dokumentu) odbieramy z limitem długości,
  pozostałe pola tekstowe ignorujemy,
- treść trafia do `SpooledTemporaryFile` (RAM do `spool_max_bytes`, potem anonimowy
  plik tymczasowy), więc nic nie zostaje na dysku po zamknięciu.

Warstwa API przekazuje `request.stream()` i nagłówek `Content-Type`. Endpoint nie może
deklarować parametru `UploadFile`, bo wtedy FastAPI wczytałby całe ciało wcześniej.
"""

import re
import tempfile
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field
from typing import IO, TYPE_CHECKING
from urllib.parse import unquote_to_bytes

from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import (
    FILE_FIELD_NAME,
    MAX_PASSWORD_BYTES,
    PASSWORD_FIELD_NAME,
)

if TYPE_CHECKING:  # TypedDict zdefiniowany w python-multipart tylko dla type checkerów
    from python_multipart.multipart import MultipartCallbacks

MAX_PART_HEADER_BYTES = 16 * 1024
"""Suma nagłówków jednej części. Chroni przed nieskończenie długimi nagłówkami."""
MAX_PARTS = 16
"""Liczba części w żądaniu (plik + ewentualne drobne pola tekstowe)."""
MAX_TEXT_FIELDS_BYTES = 64 * 1024
"""Suma rozmiarów pól tekstowych, które ignorujemy."""


@dataclass(slots=True)
class ReceivedFile:
    """Plik odebrany z żądania. Właściciel odpowiada za `close()`."""

    filename: str
    """Nazwa po normalizacji NFC i walidacji."""
    file: IO[bytes]
    size_bytes: int
    password: str | None = field(default=None, repr=False)
    """Hasło do dokumentu z pola `password`; None gdy brak lub puste. Nie logować."""

    def close(self) -> None:
        self.file.close()


FilenameCheck = Callable[[str], str]
"""Waliduje surową nazwę z nagłówka i zwraca znormalizowaną albo rzuca UploadError."""


@dataclass(slots=True)
class _Part:
    headers: dict[str, bytes] = field(default_factory=dict)
    header_bytes: int = 0
    is_file: bool = False
    is_target: bool = False
    is_password: bool = False


class _SingleFileCollector:
    def __init__(
        self,
        *,
        max_file_bytes: int,
        spool_max_bytes: int,
        tmp_dir: str | None,
        check_filename: FilenameCheck,
    ) -> None:
        self._max_file_bytes = max_file_bytes
        self._spool_max_bytes = spool_max_bytes
        self._tmp_dir = tmp_dir
        self._check_filename = check_filename

        self._parts = 0
        self._files = 0
        self._text_bytes = 0
        self._part: _Part | None = None
        self._header_field = bytearray()
        self._header_value = bytearray()
        self._password = bytearray()
        self._password_seen = False

        self.filename: str | None = None
        self.file: IO[bytes] | None = None
        self.size_bytes = 0
        self.finished = False

    def callbacks(self) -> MultipartCallbacks:
        return {
            "on_part_begin": self._on_part_begin,
            "on_header_field": self._on_header_field,
            "on_header_value": self._on_header_value,
            "on_header_end": self._on_header_end,
            "on_headers_finished": self._on_headers_finished,
            "on_part_data": self._on_part_data,
            "on_part_end": self._on_part_end,
            "on_end": self._on_end,
        }

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None

    def password(self) -> str | None:
        if not self._password:
            return None
        try:
            return self._password.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST, "Hasło musi być zakodowane w UTF-8"
            ) from exc

    # --- callbacki parsera ---------------------------------------------------------------

    def _on_part_begin(self) -> None:
        self._parts += 1
        if self._parts > MAX_PARTS:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST, f"Żądanie ma więcej niż {MAX_PARTS} części"
            )
        self._part = _Part()

    def _on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._count_header_bytes(end - start)
        self._header_field += data[start:end]

    def _on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._count_header_bytes(end - start)
        self._header_value += data[start:end]

    def _on_header_end(self) -> None:
        part = self._require_part()
        part.headers[self._header_field.decode("latin-1").strip().lower()] = bytes(
            self._header_value
        )
        self._header_field.clear()
        self._header_value.clear()

    def _on_headers_finished(self) -> None:
        part = self._require_part()
        disposition = part.headers.get("content-disposition")
        if disposition is None:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST,
                "Część żądania nie ma nagłówka Content-Disposition",
            )
        name, raw_filename = _parse_content_disposition(disposition)
        if raw_filename is None:
            if name == PASSWORD_FIELD_NAME:
                if self._password_seen:
                    raise UploadError(
                        UploadErrorCode.MALFORMED_REQUEST,
                        f"Pole '{PASSWORD_FIELD_NAME}' występuje więcej niż raz",
                    )
                self._password_seen = True
                part.is_password = True
            return  # inne pola tekstowe ignorujemy, ale liczymy ich rozmiar

        part.is_file = True
        self._files += 1
        if self._files > 1:
            raise UploadError(
                UploadErrorCode.TOO_MANY_FILES, "Żądanie zawiera więcej niż jeden plik"
            )
        if name != FILE_FIELD_NAME:
            raise UploadError(
                UploadErrorCode.FILE_MISSING,
                f"Plik musi być przesłany w polu '{FILE_FIELD_NAME}', otrzymano '{name or ''}'",
            )
        if not raw_filename:
            raise UploadError(UploadErrorCode.FILE_MISSING, "Nie wybrano pliku (pusta nazwa)")

        self.filename = self._check_filename(raw_filename)
        part.is_target = True
        self.file = tempfile.SpooledTemporaryFile(  # noqa: SIM115 - zamykany przez właściciela
            max_size=self._spool_max_bytes, mode="w+b", dir=self._tmp_dir
        )

    def _on_part_data(self, data: bytes, start: int, end: int) -> None:
        part = self._require_part()
        length = end - start
        if part.is_target:
            if self.file is None:
                raise UploadError(
                    UploadErrorCode.MALFORMED_REQUEST, "Niepoprawna struktura multipart"
                )
            self.size_bytes += length
            if self.size_bytes > self._max_file_bytes:
                raise UploadError(
                    UploadErrorCode.FILE_TOO_LARGE,
                    f"Plik przekracza limit {_format_bytes(self._max_file_bytes)}",
                )
            self.file.write(data[start:end])
        elif part.is_password:
            self._password += data[start:end]
            if len(self._password) > MAX_PASSWORD_BYTES:
                raise UploadError(
                    UploadErrorCode.MALFORMED_REQUEST,
                    f"Hasło jest dłuższe niż {MAX_PASSWORD_BYTES} bajtów",
                )
        elif not part.is_file:
            self._text_bytes += length
            if self._text_bytes > MAX_TEXT_FIELDS_BYTES:
                raise UploadError(
                    UploadErrorCode.MALFORMED_REQUEST, "Pola tekstowe żądania są za duże"
                )

    def _on_part_end(self) -> None:
        self._part = None

    def _on_end(self) -> None:
        self.finished = True

    # --- pomocnicze ----------------------------------------------------------------------

    def _require_part(self) -> _Part:
        if self._part is None:
            raise UploadError(UploadErrorCode.MALFORMED_REQUEST, "Niepoprawna struktura multipart")
        return self._part

    def _count_header_bytes(self, length: int) -> None:
        part = self._require_part()
        part.header_bytes += length
        if part.header_bytes > MAX_PART_HEADER_BYTES:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST, "Nagłówki części żądania są za długie"
            )


_TOKEN = rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
_DISPOSITION_TYPE_RE = re.compile(rb"\s*(" + _TOKEN + rb")\s*")
_PARAM_RE = re.compile(rb";\s*(" + _TOKEN + rb')\s*=\s*(?:"([^"]*)"|([^;\s]*))\s*')
_EXT_VALUE_RE = re.compile(rb"([!#$&+^`{}~0-9A-Za-z-]+)'[^']*'(.*)", re.DOTALL)


def _parse_content_disposition(raw: bytes) -> tuple[str | None, str | None]:
    """Zwraca (name, filename) z nagłówka Content-Disposition części.

    Własny parser, bo `python_multipart.parse_options_header` obcina wszystko do ostatniego
    `\\` (np. `C:\\a\\b.pdf` → `b.pdf`) i pomija `filename*`. To ukrywałoby niedozwolone znaki
    `\\` i `:` w nazwie. Wartości w cudzysłowie bierzemy dosłownie, jak w HTML5 (przeglądarki
    kodują `"` jako `%22`, a `\\` przesyłają bez zmian).
    """
    head = _DISPOSITION_TYPE_RE.match(raw)
    if head is None or head.group(1).lower() != b"form-data":
        raise UploadError(UploadErrorCode.MALFORMED_REQUEST, "Część żądania nie jest form-data")
    params: dict[bytes, bytes] = {}
    pos = head.end()
    while pos < len(raw):
        match = _PARAM_RE.match(raw, pos)
        if match is None:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST, "Niepoprawny nagłówek Content-Disposition"
            )
        key = match.group(1).lower()
        if key in params:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST,
                f"Powtórzony parametr '{key.decode()}' w Content-Disposition",
            )
        params[key] = match.group(2) if match.group(2) is not None else match.group(3)
        pos = match.end()

    name = params.get(b"name")
    return (
        _decode_text(name) if name is not None else None,
        _decode_filename(params),
    )


def _decode_filename(params: dict[bytes, bytes]) -> str | None:
    """`filename*` (RFC 5987/6266) ma pierwszeństwo przed `filename`; None = pole tekstowe."""
    extended = params.get(b"filename*")
    if extended is not None:
        match = _EXT_VALUE_RE.fullmatch(extended)
        if match is None:
            raise UploadError(UploadErrorCode.MALFORMED_REQUEST, "Niepoprawny parametr filename*")
        charset = match.group(1).decode("ascii").lower()
        if charset not in {"utf-8", "iso-8859-1"}:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST, f"Nieobsługiwane kodowanie nazwy: {charset}"
            )
        try:
            return unquote_to_bytes(match.group(2)).decode(charset)
        except UnicodeDecodeError as exc:
            raise UploadError(
                UploadErrorCode.MALFORMED_REQUEST, "Nazwa pliku ma niepoprawne kodowanie"
            ) from exc
    raw = params.get(b"filename")
    return _decode_text(raw) if raw is not None else None


def _decode_text(raw: bytes) -> str:
    """Przeglądarki i curl wysyłają UTF-8; latin-1 jako ostatnia deska ratunku."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _format_bytes(size: int) -> str:
    mib = size / (1024 * 1024)
    return f"{mib:g} MB" if mib >= 1 else f"{size} B"


def _boundary(content_type: str | None) -> bytes:
    if not content_type:
        raise UploadError(UploadErrorCode.MALFORMED_REQUEST, "Brak nagłówka Content-Type")
    mime, params = parse_options_header(content_type)
    if mime != b"multipart/form-data":
        raise UploadError(
            UploadErrorCode.MALFORMED_REQUEST,
            "Żądanie musi mieć typ multipart/form-data z polem 'file'",
        )
    boundary = params.get(b"boundary")
    if not boundary or len(boundary) > 70:  # RFC 2046: 1-70 znaków
        raise UploadError(UploadErrorCode.MALFORMED_REQUEST, "Niepoprawny parametr boundary")
    return boundary


async def receive_single_file(
    chunks: AsyncIterable[bytes],
    content_type: str | None,
    *,
    max_file_bytes: int,
    spool_max_bytes: int,
    check_filename: FilenameCheck,
    tmp_dir: str | None = None,
) -> ReceivedFile:
    """Odbiera dokładnie jeden plik z pola `file`, przerywając przy pierwszym naruszeniu."""
    parser_max = max_file_bytes + MAX_PARTS * MAX_PART_HEADER_BYTES + MAX_TEXT_FIELDS_BYTES
    collector = _SingleFileCollector(
        max_file_bytes=max_file_bytes,
        spool_max_bytes=spool_max_bytes,
        tmp_dir=tmp_dir,
        check_filename=check_filename,
    )
    parser = MultipartParser(_boundary(content_type), collector.callbacks(), max_size=parser_max)
    try:
        async for chunk in chunks:
            if chunk:
                parser.write(chunk)
        parser.finalize()
    except UploadError:
        collector.close()
        raise
    except MultipartParseError as exc:
        collector.close()
        raise UploadError(
            UploadErrorCode.MALFORMED_REQUEST, "Niepoprawna struktura multipart"
        ) from exc
    except BaseException:
        collector.close()
        raise

    if collector.file is None or collector.filename is None:
        raise UploadError(
            UploadErrorCode.FILE_MISSING, f"Żądanie nie zawiera pliku w polu '{FILE_FIELD_NAME}'"
        )
    if not collector.finished:
        collector.close()
        raise UploadError(UploadErrorCode.MALFORMED_REQUEST, "Żądanie multipart jest niekompletne")
    if collector.size_bytes == 0:
        collector.close()
        raise UploadError(UploadErrorCode.FILE_EMPTY, "Przesłany plik ma 0 bajtów")

    try:
        password = collector.password()
    except UploadError:
        collector.close()
        raise

    collector.file.seek(0)
    return ReceivedFile(
        filename=collector.filename,
        file=collector.file,
        size_bytes=collector.size_bytes,
        password=password,
    )
