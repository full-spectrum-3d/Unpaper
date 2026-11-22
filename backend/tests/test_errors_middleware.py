"""Nieobsłużony wyjątek → 500 problem+json z nagłówkami CORS; request_id nadaje serwer."""

import asyncio
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.unit.fakes import FakeLlmClient

ORIGIN = "http://localhost:8080"


def _client() -> TestClient:
    app = create_app(
        Settings(app_env="development", auth_enabled=False, _env_file=None),
        llm_client=FakeLlmClient(),
        converter=None,
    )

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("awaria")

    return TestClient(app)


def test_unhandled_error_is_problem_json_with_cors(caplog: pytest.LogCaptureFixture) -> None:
    with _client() as client:
        response = client.get("/boom", headers={"Origin": ORIGIN})
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["access-control-allow-origin"] == ORIGIN
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR" and body["request_id"]
    assert "Nieobsłużony wyjątek" in caplog.text


def test_client_request_id_is_not_trusted_but_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="app")
    sent = str(uuid.uuid4())
    with _client() as client:
        response = client.get("/api/v1/health/live", headers={"X-Request-ID": sent})
    assert response.headers["X-Request-ID"] != sent
    assert uuid.UUID(response.headers["X-Request-ID"])
    assert f"client_request_id={sent}" in caplog.text


def test_shutdown_awaits_cancelled_warm_up() -> None:
    finished: list[Any] = []

    class SlowWarmUp(FakeLlmClient):
        async def warm_up(self, model: str, messages: Any = None) -> None:
            try:
                await asyncio.sleep(60)
            finally:
                finished.append(model)

        async def aclose(self) -> None:
            finished.append("aclose")

    app = create_app(
        Settings(app_env="development", auth_enabled=False, _env_file=None),
        llm_client=SlowWarmUp(),
        converter=None,
    )
    with TestClient(app) as client:
        client.get("/api/v1/health/live")  # pętla zdąży uruchomić zadanie rozgrzewania
    assert finished == ["qwen3:8b", "aclose"]
