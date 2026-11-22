from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.health import missing_tools
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
    models: set[str] | Exception,
    converter: LibreOfficeConverter | None = _CONVERTER,
    missing: list[str] | None = None,
    **settings: Any,
) -> Any:
    fake = FakeLlmClient(models=models)
    app = create_app(
        Settings(app_env="development", auth_enabled=False, _env_file=None, **settings),
        llm_client=fake,
        converter=converter,
    )
    # Sonda libmagic/Tesseracta zależy od maszyny - w testach podstawiamy wynik.
    app.dependency_overrides[missing_tools] = lambda: missing or []
    with TestClient(app) as client:
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
    response, _ = _ready(LlmUnavailableError("refused http://llm:11434"))
    assert response.status_code == 503 and response.json()["code"] == "LLM_UNAVAILABLE"
    assert "llm:11434" not in response.text  # szczegóły tylko w logach


def test_ready_missing_system_tools() -> None:
    response, _ = _ready({"qwen3:8b"}, missing=["libmagic", "tesseract"])
    assert response.status_code == 503 and response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert "libmagic" not in response.text


@pytest.mark.parametrize(
    ("configured", "available"),
    [("qwen3", {"qwen3:latest"}), ("qwen3:latest", {"qwen3"})],
)
def test_ready_model_without_tag_means_latest(configured: str, available: set[str]) -> None:
    response, _ = _ready(available, llm_model=configured)
    assert response.status_code == 200


def test_missing_tools_reports_absent_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.v1.health as health

    monkeypatch.setattr(health.shutil, "which", lambda _name: None)
    assert "tesseract" in missing_tools()


def test_convert_params() -> None:
    with TestClient(create_app(_settings(), llm_client=FakeLlmClient())) as client:
        spec = client.get("/openapi.json").json()
    params = spec["paths"]["/api/v1/forms/convert"]["post"]["parameters"]
    assert [p["name"] for p in params] == ["report", "model", "identitySource"]


def test_docs_disabled_in_production() -> None:
    settings = Settings(
        jwt_secret="s" * 40,
        api_user="api",
        api_password_hash="$argon2id$x",  # noqa: S106 - walidacja sprawdza tylko prefiks
        _env_file=None,
    )
    app = create_app(settings, llm_client=FakeLlmClient(), converter=None)
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
    assert "/api/v1/forms/convert" in app.openapi()["paths"]  # eksport schematu działa


def test_openapi_documents_ready_failure() -> None:
    spec = create_app(_settings(), llm_client=FakeLlmClient(), converter=None).openapi()
    responses = spec["paths"]["/api/v1/health/ready"]["get"]["responses"]
    assert set(responses) == {"200", "500", "503"}
    assert "application/problem+json" in responses["503"]["content"]
    ready = spec["components"]["schemas"]["ReadyResponse"]["properties"]
    assert set(ready) == {"status", "degraded"}
