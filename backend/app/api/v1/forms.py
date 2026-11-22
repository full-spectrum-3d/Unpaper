"""POST /forms/convert, POST /forms/validate (spec §6.1-6.3).

`/forms/convert` czyta ciało żądania strumieniowo (`request.stream()`), bez parametru
`UploadFile`: FastAPI wczytałby wtedy cały plik przed walidacją nazwy i rozmiaru.
Opis ciała multipart w OpenAPI podajemy ręcznie (`openapi_extra`).
"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated, Any, Literal

import anyio.to_thread
from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.v1.schemas import ConvertResponse, ValidationResult
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.openapi import problem_responses
from app.pipeline.convert import convert_upload, upload_limits
from app.pipeline.llm_client import LlmClient, get_llm_client
from app.pipeline.upload_validation import UploadError, accept_upload
from app.pipeline.verify import verify_form

router = APIRouter(prefix="/forms", tags=["forms"])

WARNINGS_HEADER = "X-Conversion-Warnings"

_MULTIPART_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "Dokładnie jeden plik: pdf, doc, docx, ods, xlsx, "
                            "jpg, jpeg albo png",
                        },
                        "password": {
                            "type": "string",
                            "description": "Hasło do dokumentu zabezpieczonego hasłem "
                            "(po odpowiedzi DOCUMENT_PASSWORD_REQUIRED)",
                        },
                    },
                }
            }
        },
    }
}


_CONVERT_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "model": ConvertResponse,
        "description": "Domyślnie sama konfiguracja formularza w formacie importu (spec §7); "
        "przy `report=true` obiekt `{form, report}` (`ConvertWithReport`).",
        "headers": {
            WARNINGS_HEADER: {
                "schema": {"type": "integer"},
                "description": "Liczba ostrzeżeń konwersji (jak `report.warnings`)",
            }
        },
    },
    **problem_responses(
        ErrorCode.MALFORMED_REQUEST,
        ErrorCode.FILE_MISSING,
        ErrorCode.TOO_MANY_FILES,
        ErrorCode.FILENAME_TOO_LONG,
        ErrorCode.FILENAME_FORBIDDEN_CHARS,
        ErrorCode.FILE_EMPTY,
        ErrorCode.FILE_TOO_LARGE,
        ErrorCode.UNSUPPORTED_EXTENSION,
        ErrorCode.MIME_MISMATCH,
        ErrorCode.ARCHIVE_TOO_LARGE,
        ErrorCode.DOCUMENT_TOO_COMPLEX,
        ErrorCode.DOCUMENT_UNREADABLE,
        ErrorCode.DOCUMENT_PASSWORD_REQUIRED,
        ErrorCode.DOCUMENT_PASSWORD_INVALID,
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.SERVER_BUSY,
        ErrorCode.PROCESSING_TIMEOUT,
    ),
}

_VALIDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "model": ValidationResult,
        "description": "Wynik weryfikacji: JSON Schema i reguły R01-R16, bez autonaprawy. "
        "Formularz z błędami też daje 200 - o poprawności mówi pole `valid`.",
    },
    **problem_responses(
        ErrorCode.FILE_TOO_LARGE,
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.SERVER_BUSY,
        instance="/api/v1/forms/validate",
    ),
}

RETRY_AFTER_S = 30


@asynccontextmanager
async def _job_slot(semaphore: asyncio.Semaphore, deadline: float) -> AsyncIterator[None]:
    """Miejsce w limicie MAX_CONCURRENT_JOBS; czekanie wlicza się do czasu żądania."""
    try:
        async with asyncio.timeout(max(deadline - time.monotonic(), 0)):
            await semaphore.acquire()
    except TimeoutError as exc:
        raise AppError(
            ErrorCode.SERVER_BUSY,
            "Serwer przetwarza inne pliki - spróbuj ponownie",
            headers={"Retry-After": str(RETRY_AFTER_S)},
        ) from exc
    try:
        yield
    finally:
        semaphore.release()


@router.post(
    "/convert",
    summary="Konwersja dokumentu na formularz",
    response_model=None,
    responses=_CONVERT_RESPONSES,
    openapi_extra=_MULTIPART_BODY,
)
async def convert(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[LlmClient, Depends(get_llm_client)],
    report: Annotated[bool, Query(description="Dołącz raport konwersji (spec §6.2)")] = False,
    model: Annotated[
        str | None,
        Query(description="Model LLM z `LLM_MODEL` albo `LLM_MODELS`; domyślnie `LLM_MODEL`"),
    ] = None,
    identity_source: Annotated[
        Literal["PESEL", "MLPZ"] | None,
        Query(
            alias="identitySource",
            description="Źródło imienia, nazwiska i PESEL w sekcji „Twoje dane”; "
            "domyślnie INITIAL_DATA_IDENTITY_SOURCE",
        ),
    ] = None,
) -> JSONResponse:
    """Przyjmuje dokładnie jeden plik (`multipart/form-data`, pole `file`) i zwraca
    konfigurację formularza w formacie importu Generatora Formularzy COI.

    Obsługiwane formaty: PDF (warstwa tekstowa albo skan z OCR), DOC, DOCX, ODS, XLSX,
    JPG, JPEG, PNG. DOC i ODS wymagają LibreOffice w obrazie (bez niego 415).

    Przebieg: walidacja pliku → odczyt treści → analiza modelem LLM (przy jego awarii
    reguły, ostrzeżenie `W01_LLM_FALLBACK`) → budowa formularza → weryfikacja reguł
    z autonaprawą. Odpowiedź 200 zawsze zawiera formularz, który przechodzi weryfikację.

    Dokument zaszyfrowany hasłem daje 422 `DOCUMENT_PASSWORD_REQUIRED`; wyślij go
    ponownie z polem `password`. Konwersja trwa zwykle od kilku sekund do kilku minut
    (limit `REQUEST_TIMEOUT_S`).
    """
    deadline = time.monotonic() + settings.request_timeout_s
    if model is not None and model != settings.llm_model:
        if model not in settings.llm_allowed_models:
            allowed = ", ".join(settings.llm_allowed_models)
            raise AppError(
                ErrorCode.VALIDATION_ERROR, f"Nieznany model {model!r}; dozwolone: {allowed}"
            )
        settings = settings.model_copy(update={"llm_model": model})
    try:
        # Odbiór (wolny klient) i walidacja też mieszczą się w REQUEST_TIMEOUT_S.
        async with asyncio.timeout(settings.request_timeout_s):
            upload = await accept_upload(
                request.stream(),
                request.headers.get("content-type"),
                upload_limits(settings),
                cpu_slot=_job_slot(request.app.state.validation_semaphore, deadline),
            )
    except UploadError as exc:
        raise AppError(ErrorCode(exc.code), exc.detail) from exc
    except TimeoutError as exc:
        raise AppError(ErrorCode.PROCESSING_TIMEOUT) from exc

    with upload:
        async with _job_slot(request.app.state.job_semaphore, deadline):
            result = await convert_upload(
                upload,
                settings=settings,
                client=client,
                converter=request.app.state.converter,
                deadline=deadline,
                identity_source=identity_source,
            )
    content: dict[str, Any] = (
        {"form": result.form, "report": result.report} if report else result.form
    )
    return JSONResponse(content, headers={WARNINGS_HEADER: str(len(result.warnings))})


@router.post(
    "/validate",
    summary="Weryfikacja JSON-a formularza",
    response_model=None,
    responses=_VALIDATE_RESPONSES,
)
async def validate(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    form: Annotated[
        dict[str, Any], Body(description="Konfiguracja formularza w formacie importu (spec §7)")
    ],
) -> dict[str, Any]:
    """Sprawdza dowolny JSON formularza tymi samymi regułami co konwersja, ale niczego
    nie poprawia. Przydatne po ręcznej edycji formularza, przed importem do Generatora.

    Ciało musi być obiektem JSON (inaczej 422 `VALIDATION_ERROR`).
    """
    deadline = time.monotonic() + settings.request_timeout_s
    # Wątku nie da się przerwać, więc limit czasu dotyczy czekania na miejsce w semaforze.
    async with _job_slot(request.app.state.validation_semaphore, deadline):
        checked = await anyio.to_thread.run_sync(partial(verify_form, form, autofix=False))
    return {
        "valid": checked.valid,
        "errors": [issue.to_dict() for issue in checked.errors],
        "warnings": [w.model_dump(exclude_none=True) for w in checked.warnings],
    }
