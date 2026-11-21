from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.pipeline.llm_client import LlmUnavailableError
from tests.unit.fakes import FakeLlmClient


def _settings() -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None)


def _ready(models: set[str] | Exception) -> Any:
    fake = FakeLlmClient(models=models)
    with TestClient(create_app(_settings(), llm_client=fake)) as client:
        return client.get("/api/v1/health/ready"), fake


def test_live(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200


def test_ready_ok() -> None:
    response, fake = _ready({"qwen3:8b", "qwen3:4b"})
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    assert fake.warmed == ["qwen3:8b"]


def test_ready_degraded() -> None:
    response, _ = _ready({"qwen3:8b"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "degraded": ["fast"]}


def test_ready_default_model_missing() -> None:
    response, _ = _ready({"qwen3:4b"})
    assert response.status_code == 503
    assert response.json()["code"] == "LLM_UNAVAILABLE"
    assert response.headers["content-type"].startswith("application/problem+json")


def test_ready_llm_down() -> None:
    response, _ = _ready(LlmUnavailableError("refused"))
    assert response.status_code == 503 and response.json()["code"] == "LLM_UNAVAILABLE"


def test_convert_accepts_mode_param() -> None:
    with TestClient(create_app(_settings(), llm_client=FakeLlmClient())) as client:
        spec = client.get("/openapi.json").json()
    params = spec["paths"]["/api/v1/forms/convert"]["post"]["parameters"]
    mode = next(p for p in params if p["name"] == "mode")
    schema = mode["schema"]
    options = schema.get("anyOf", [schema])
    assert any(o.get("enum") == ["accurate", "fast"] for o in options)
