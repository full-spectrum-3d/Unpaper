from typing import Any

from app.core.config import Settings


def _settings(**kw: Any) -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None, **kw)


def test_llm_defaults() -> None:
    s = _settings()
    assert (s.llm_timeout_s, s.request_timeout_s, s.llm_model) == (240, 540, "qwen3:8b")
