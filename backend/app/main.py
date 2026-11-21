"""Fabryka aplikacji FastAPI (spec §4.2, §6).

Uruchomienie: `uvicorn app.main:create_app --factory`.
"""

from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, catalog, forms, health
from app.core.config import Settings, load_settings
from app.core.errors import (
    REQUEST_ID_HEADER,
    ProblemDetail,
    install_error_handlers,
    request_id_middleware,
)
from app.core.security import require_auth

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="COI - Cyfryzacja formularzy", version="0.1.0")
    app.state.settings = settings

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "X-Conversion-Warnings"],
    )
    # Dodany jako ostatni = najbardziej zewnętrzny: request_id jest dostępny wszędzie.
    app.middleware("http")(request_id_middleware)

    public_routers: list[APIRouter] = [health.router]
    if settings.token_issuing_enabled:
        public_routers.append(auth.router)
    # Każdy nowy router trafia tutaj, chyba że świadomie ma być publiczny.
    protected_routers: list[APIRouter] = [forms.router, catalog.router]

    for router in public_routers:
        app.include_router(router, prefix=API_PREFIX)
    auth_responses: dict[int | str, dict[str, Any]] = {
        401: {"model": ProblemDetail, "description": "Brak lub nieprawidłowy token"},
        403: {"model": ProblemDetail, "description": "Token bez wymaganej roli"},
    }
    for router in protected_routers:
        app.include_router(
            router,
            prefix=API_PREFIX,
            dependencies=[Depends(require_auth)],
            responses=auth_responses,
        )

    return app
