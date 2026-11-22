"""Wspólny format błędów API: application/problem+json, RFC 9457 (spec §6.4).

Każdy błąd domenowy to `AppError` z kodem z `ErrorCode`. Nowe kody dopisujemy do
`ErrorCode` i `_ERROR_META` - handlery i format odpowiedzi są wspólne.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_TYPE_BASE = "https://coi-cf/errors/"
PROBLEM_MEDIA_TYPE = "application/problem+json"
REQUEST_ID_HEADER = "X-Request-ID"


class ErrorCode(StrEnum):
    # Uwierzytelnianie (spec §10.1)
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105 - kod błędu, nie sekret
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    FORBIDDEN = "FORBIDDEN"
    # Walidacja pliku (spec §6.3); te same wartości co `UploadErrorCode`
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
    DOCUMENT_PASSWORD_REQUIRED = "DOCUMENT_PASSWORD_REQUIRED"  # noqa: S105 - kod, nie hasło
    DOCUMENT_PASSWORD_INVALID = "DOCUMENT_PASSWORD_INVALID"  # noqa: S105 - kod, nie hasło
    # Przetwarzanie (spec §6.4)
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    SERVER_BUSY = "SERVER_BUSY"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    # Ogólne
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_ERROR_META: dict[ErrorCode, tuple[HTTPStatus, str]] = {
    ErrorCode.NOT_AUTHENTICATED: (HTTPStatus.UNAUTHORIZED, "Wymagane uwierzytelnienie"),
    ErrorCode.INVALID_TOKEN: (HTTPStatus.UNAUTHORIZED, "Nieprawidłowy lub wygasły token"),
    ErrorCode.INVALID_CREDENTIALS: (HTTPStatus.UNAUTHORIZED, "Nieprawidłowy login lub hasło"),
    ErrorCode.FORBIDDEN: (HTTPStatus.FORBIDDEN, "Brak uprawnień"),
    ErrorCode.MALFORMED_REQUEST: (HTTPStatus.BAD_REQUEST, "Niepoprawne żądanie multipart"),
    ErrorCode.FILE_MISSING: (HTTPStatus.BAD_REQUEST, "Brak pliku w żądaniu"),
    ErrorCode.TOO_MANY_FILES: (HTTPStatus.BAD_REQUEST, "Przesłano więcej niż jeden plik"),
    ErrorCode.FILENAME_TOO_LONG: (HTTPStatus.BAD_REQUEST, "Zbyt długa nazwa pliku"),
    ErrorCode.FILENAME_FORBIDDEN_CHARS: (
        HTTPStatus.BAD_REQUEST,
        "Niedozwolone znaki w nazwie pliku",
    ),
    ErrorCode.FILE_TOO_LARGE: (HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Plik jest zbyt duży"),
    ErrorCode.FILE_EMPTY: (HTTPStatus.BAD_REQUEST, "Plik jest pusty"),
    ErrorCode.UNSUPPORTED_EXTENSION: (
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        "Nieobsługiwany format pliku",
    ),
    ErrorCode.MIME_MISMATCH: (
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        "Zawartość pliku nie odpowiada rozszerzeniu",
    ),
    ErrorCode.ARCHIVE_TOO_LARGE: (
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "Plik po rozpakowaniu jest zbyt duży",
    ),
    ErrorCode.DOCUMENT_TOO_COMPLEX: (
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "Dokument jest zbyt złożony",
    ),
    ErrorCode.DOCUMENT_UNREADABLE: (
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "Nie można odczytać dokumentu",
    ),
    ErrorCode.DOCUMENT_PASSWORD_REQUIRED: (
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "Dokument jest zabezpieczony hasłem",
    ),
    ErrorCode.DOCUMENT_PASSWORD_INVALID: (
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "Niepoprawne hasło do dokumentu",
    ),
    ErrorCode.LLM_UNAVAILABLE: (HTTPStatus.SERVICE_UNAVAILABLE, "Model AI jest niedostępny"),
    ErrorCode.PROCESSING_TIMEOUT: (
        HTTPStatus.GATEWAY_TIMEOUT,
        "Przekroczono czas przetwarzania",
    ),
    ErrorCode.SERVER_BUSY: (
        HTTPStatus.SERVICE_UNAVAILABLE,
        "Serwer jest zajęty, spróbuj ponownie za chwilę",
    ),
    ErrorCode.SERVICE_UNAVAILABLE: (
        HTTPStatus.SERVICE_UNAVAILABLE,
        "Brak wymaganych komponentów serwera",
    ),
    ErrorCode.VALIDATION_ERROR: (HTTPStatus.UNPROCESSABLE_CONTENT, "Niepoprawne dane żądania"),
    ErrorCode.NOT_FOUND: (HTTPStatus.NOT_FOUND, "Nie znaleziono zasobu"),
    ErrorCode.METHOD_NOT_ALLOWED: (HTTPStatus.METHOD_NOT_ALLOWED, "Metoda niedozwolona"),
    ErrorCode.HTTP_ERROR: (HTTPStatus.BAD_REQUEST, "Błąd żądania"),
    ErrorCode.INTERNAL_ERROR: (HTTPStatus.INTERNAL_SERVER_ERROR, "Wewnętrzny błąd serwera"),
}


class ProblemDetail(BaseModel):
    """Treść odpowiedzi błędu (RFC 9457) rozszerzona o `code` i `request_id`."""

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    instance: str | None = None
    request_id: str | None = None
    errors: list[dict[str, Any]] | None = None


def problem_doc(description: str) -> dict[str, Any]:
    """Opis odpowiedzi błędu do `responses=` endpointu: problem+json ze schematem ProblemDetail."""
    return {
        "description": description,
        "content": {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/ProblemDetail"}}},
    }


class AppError(Exception):
    """Błąd domenowy zamieniany na odpowiedź problem+json."""

    def __init__(
        self,
        code: ErrorCode,
        detail: str | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        status, title = _ERROR_META[code]
        super().__init__(detail or title)
        self.code = code
        self.status = int(status)
        self.title = title
        self.detail = detail
        self.headers = dict(headers or {})


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def problem_response(
    request: Request,
    *,
    code: ErrorCode,
    status: int | None = None,
    title: str | None = None,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    default_status, default_title = _ERROR_META[code]
    request_id = _request_id(request)
    problem = ProblemDetail(
        type=f"{PROBLEM_TYPE_BASE}{code}",
        title=title or default_title,
        status=status or int(default_status),
        code=code,
        detail=detail,
        instance=request.url.path,
        request_id=request_id,
        errors=errors,
    )
    response_headers = dict(headers or {})
    if request_id:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=response_headers,
    )


async def _handle_app_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)  # noqa: S101 - gwarantowane przez rejestrację handlera
    return problem_response(
        request,
        code=exc.code,
        detail=exc.detail,
        headers=exc.headers,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    # Tylko lokalizacja, komunikat i typ - bez `input`, który może zawierać np. hasło.
    errors = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return problem_response(request, code=ErrorCode.VALIDATION_ERROR, errors=errors)


async def _handle_http_exception(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    match exc.status_code:
        case HTTPStatus.NOT_FOUND:
            code = ErrorCode.NOT_FOUND
        case HTTPStatus.METHOD_NOT_ALLOWED:
            code = ErrorCode.METHOD_NOT_ALLOWED
        case HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
            code = ErrorCode.FILE_TOO_LARGE  # limit `max_body_size` aplikacji
        case _:
            code = ErrorCode.HTTP_ERROR
    try:
        title = HTTPStatus(exc.status_code).phrase
    except ValueError:
        title = None
    return problem_response(
        request,
        code=code,
        status=exc.status_code,
        title=title if code is ErrorCode.HTTP_ERROR else None,
        headers=exc.headers,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> Response:
    logger.exception(
        "Nieobsłużony wyjątek",
        extra={"request_id": _request_id(request), "path": request.url.path},
    )
    return problem_response(request, code=ErrorCode.INTERNAL_ERROR)


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Nadaje żądaniu `request_id` i zamienia nieobsłużone wyjątki na problem+json.

    Identyfikator zawsze generuje serwer; poprawny UUID z nagłówka klienta tylko logujemy
    (`client_request_id`), żeby dało się powiązać zgłoszenie z logami.
    Middleware leży wewnątrz `CORSMiddleware`, więc odpowiedź 500 dostaje nagłówki CORS
    (handler `Exception` Starlette działa poza wszystkimi middleware).
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        client_request_id = str(uuid.UUID(request.headers.get(REQUEST_ID_HEADER, "")))
    except ValueError:
        pass
    else:
        logger.info(
            "request_id=%s client_request_id=%s",
            request_id,
            client_request_id,
            extra={"request_id": request_id, "client_request_id": client_request_id},
        )
    try:
        response = await call_next(request)
    except Exception as exc:  # ostatnia linia obrony; handler loguje wyjątek
        return await _handle_unexpected(request, exc)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
