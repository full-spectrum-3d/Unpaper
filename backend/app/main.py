"""Fabryka aplikacji FastAPI (spec §4.2, §6).

Uruchomienie: `uvicorn app.main:create_app --factory`.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, catalog, forms, health
from app.core.config import Settings, load_settings
from app.core.errors import (
    REQUEST_ID_HEADER,
    ErrorCode,
    install_error_handlers,
    request_id_middleware,
)
from app.core.logging import configure_logging
from app.core.openapi import (
    API_DESCRIPTION,
    OPENAPI_TAGS,
    SWAGGER_UI_PARAMETERS,
    install_openapi,
    problem_responses,
)
from app.core.security import require_auth
from app.core.users import UserStore
from app.pipeline.analyze import prompt_messages
from app.pipeline.converter import Converter, find_converter
from app.pipeline.llm_client import LlmClient, LlmError, OllamaClient

API_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


async def _warm_up(client: LlmClient, model: str) -> None:
    """Ładuje model trybu domyślnego do pamięci; błąd nie blokuje startu."""
    try:
        await client.warm_up(model, prompt_messages(""))
    except LlmError as exc:
        logger.warning("nie udało się rozgrzać modelu %s: %s", model, exc)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if app.state.llm_client is None:
        app.state.llm_client = OllamaClient(settings)
    client: LlmClient = app.state.llm_client
    model = settings.llm_model
    app.state.warm_up_task = asyncio.create_task(_warm_up(client, model))
    try:
        yield
    finally:
        app.state.warm_up_task.cancel()
        # Zadanie musi się zakończyć przed zamknięciem klienta, którego używa.
        with suppress(asyncio.CancelledError):
            await app.state.warm_up_task
        await client.aclose()


def create_app(
    settings: Settings | None = None,
    llm_client: LlmClient | None = None,
    converter: Converter | Literal["auto"] | None = "auto",
) -> FastAPI:
    """`converter="auto"`: szukamy `soffice` w PATH; `None` = Plan B (DOC/ODS → 415)."""
    settings = settings or load_settings()
    configure_logging(settings.log_level)

    # Na produkcji bez /docs, /redoc i /openapi.json; eksport schematu woła `app.openapi()`.
    docs = settings.app_env != "production"
    app = FastAPI(
        title="COI - Cyfryzacja formularzy",
        version="0.1.0",
        summary="Konwersja dokumentów na formularze Generatora Formularzy COI",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        # Każdy endpoint może skończyć się nieoczekiwanym błędem 500 w formacie problem+json.
        responses=problem_responses(ErrorCode.INTERNAL_ERROR, instance="/api/v1/forms/convert"),
        lifespan=_lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        # Body JSON jest czytane przed `require_auth`: bez limitu anonim może wysłać
        # dowolnie duże żądanie. +1 MiB na narzut multipart (jak `client_max_body_size` w nginx).
        max_body_size=(settings.max_file_size_mb + 1) * 1024 * 1024,
    )
    app.state.settings = settings
    app.state.llm_client = llm_client
    app.state.converter = find_converter(settings) if converter == "auto" else converter
    # Limit równoległych konwersji (spec §10.2): Ollama na CPU i tak liczy po kolei.
    app.state.job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
    # Osobny, większy limit na walidację CPU (upload, /forms/validate): nie czeka za LLM.
    app.state.validation_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs * 2)
    app.state.user_store = (
        UserStore(settings.users_db_path)
        if settings.registration_available and settings.users_db_path is not None
        else None
    )

    install_error_handlers(app)
    install_openapi(app)
    # Wewnątrz CORS: request_id i konwersja wyjątków na 500 problem+json z nagłówkami CORS.
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "X-Conversion-Warnings"],
    )

    public_routers: list[APIRouter] = [health.router]
    if settings.token_issuing_enabled:
        public_routers.append(auth.router)
    # Każdy nowy router trafia tutaj, chyba że świadomie ma być publiczny.
    protected_routers: list[APIRouter] = [forms.router, catalog.router]

    for router in public_routers:
        app.include_router(router, prefix=API_PREFIX)
    auth_responses: dict[int | str, dict[str, Any]] = problem_responses(
        ErrorCode.NOT_AUTHENTICATED, ErrorCode.INVALID_TOKEN, ErrorCode.FORBIDDEN
    )
    for router in protected_routers:
        app.include_router(
            router,
            prefix=API_PREFIX,
            dependencies=[Depends(require_auth)],
            responses=auth_responses,
        )

    return app
