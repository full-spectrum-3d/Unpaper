from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.pipeline import converter as converter_module
from app.pipeline.analyze import prompt_messages
from app.pipeline.converter import LibreOfficeConverter
from app.pipeline.llm_client import LlmUnavailableError
from tests.unit.fakes import FakeLlmClient, FakeRunner

_CONVERTER = LibreOfficeConverter("soffice", 60, FakeRunner())


def _settings() -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None)


def _ready(
    models: set[str] | Exception, converter: LibreOfficeConverter | None = _CONVERTER
) -> Any:
    fake = FakeLlmClient(models=models)
    with TestClient(create_app(_settings(), llm_client=fake, converter=converter)) as client:
        return client.get("/api/v1/health/ready"), fake


def test_live(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200


def test_ready_ok() -> None:
    response, fake = _ready({"qwen3:8b"})
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    assert fake.warmed == ["qwen3:8b"]
    assert fake.warm_messages == [prompt_messages("")]


def test_ready_degraded_converter() -> None:
    response, _ = _ready({"qwen3:8b"}, converter=None)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "degraded": ["converter"]}


def test_create_app_detects_converter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(converter_module.shutil, "which", lambda _name: None)
    assert create_app(_settings(), llm_client=FakeLlmClient()).state.converter is None

    monkeypatch.setattr(converter_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    found = create_app(_settings(), llm_client=FakeLlmClient()).state.converter
    assert isinstance(found, LibreOfficeConverter)


def test_ready_model_missing() -> None:
    response, _ = _ready({"bielik:11b"})
    assert response.status_code == 503
    assert response.json()["code"] == "LLM_UNAVAILABLE"
    assert response.headers["content-type"].startswith("application/problem+json")


def test_ready_llm_down() -> None:
    response, _ = _ready(LlmUnavailableError("refused"))
    assert response.status_code == 503 and response.json()["code"] == "LLM_UNAVAILABLE"


def test_convert_has_only_report_and_identity_source_params() -> None:
    with TestClient(create_app(_settings(), llm_client=FakeLlmClient())) as client:
        spec = client.get("/openapi.json").json()
    params = spec["paths"]["/api/v1/forms/convert"]["post"]["parameters"]
    assert [p["name"] for p in params] == ["report", "identitySource"]


def test_openapi_documents_ready_failure() -> None:
    spec = create_app(_settings(), llm_client=FakeLlmClient(), converter=None).openapi()
    responses = spec["paths"]["/api/v1/health/ready"]["get"]["responses"]
    assert set(responses) == {"200", "503"}
    assert "application/problem+json" in responses["503"]["content"]
    ready = spec["components"]["schemas"]["ReadyResponse"]["properties"]
    assert set(ready) == {"status", "degraded"}
