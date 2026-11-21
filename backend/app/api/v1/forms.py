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

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode, ProblemDetail, problem_doc
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
        "description": "Konfiguracja formularza w formacie importu (spec §7) albo, przy "
        "`report=true`, obiekt `{form, report}`. Nagłówek `X-Conversion-Warnings` podaje "
        "liczbę ostrzeżeń.",
        "headers": {
            WARNINGS_HEADER: {"schema": {"type": "integer"}, "description": "Liczba ostrzeżeń"}
        },
        "content": {
            "application/json": {"schema": {"type": "object", "additionalProperties": True}}
        },
    },
    400: problem_doc("Brak pliku, kilka plików albo niedozwolona nazwa pliku"),
    413: problem_doc("Plik większy niż MAX_FILE_SIZE_MB"),
    415: problem_doc("Nieobsługiwany format albo zawartość niezgodna z rozszerzeniem"),
    422: problem_doc(
        "Dokument uszkodzony, zbyt złożony albo zabezpieczony hasłem; niepoprawne "
        "`identitySource`; model spoza LLM_MODELS"
    ),
    503: problem_doc("SERVER_BUSY: serwer przetwarza inne pliki (nagłówek Retry-After)"),
    504: problem_doc("Przekroczono REQUEST_TIMEOUT_S"),
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
    """Główny endpoint: 1 plik → JSON w formacie importu (lub `{form, report}`)."""
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
    responses={
        200: {"description": "Wynik weryfikacji: JSON Schema i reguły R01-R15, bez autonaprawy"},
        422: {"model": ProblemDetail, "description": "Ciało nie jest obiektem JSON"},
        503: problem_doc("SERVER_BUSY: serwer przetwarza inne żądania (nagłówek Retry-After)"),
    },
)
async def validate(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    form: Annotated[
        dict[str, Any], Body(description="Konfiguracja formularza w formacie importu (spec §7)")
    ],
) -> dict[str, Any]:
    """Walidacja dowolnego JSON-a formularza → `{valid, errors[], warnings[]}`."""
    deadline = time.monotonic() + settings.request_timeout_s
    # Wątku nie da się przerwać, więc limit czasu dotyczy czekania na miejsce w semaforze.
    async with _job_slot(request.app.state.validation_semaphore, deadline):
        checked = await anyio.to_thread.run_sync(partial(verify_form, form, autofix=False))
    return {
        "valid": checked.valid,
        "errors": [issue.to_dict() for issue in checked.errors],
        "warnings": [w.model_dump(exclude_none=True) for w in checked.warnings],
    }
