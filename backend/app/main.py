"""Aplikacja FastAPI: routery, middleware, handler błędów RFC 9457 (spec §4.2, §6)."""

from fastapi import FastAPI

from app.api.v1 import auth, catalog, forms, health

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(title="COI - Cyfryzacja formularzy", version="0.1.0")
    # TODO: CORS, request_id, logi JSON, handler problem+json (app.core.errors)
    for router in (auth.router, forms.router, catalog.router, health.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
