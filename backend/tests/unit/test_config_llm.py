from typing import Any

from app.core.config import Settings


def _settings(**kw: Any) -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None, **kw)


def test_llm_defaults() -> None:
    s = _settings()
    assert (s.llm_timeout_s, s.request_timeout_s, s.llm_model) == (240, 540, "qwen3:8b")


def test_llm_models_from_csv_include_default_once() -> None:
    s = _settings(llm_models="qwen3.5:35b-a3b, qwen3:8b")
    assert s.llm_allowed_models == ["qwen3:8b", "qwen3.5:35b-a3b"]
