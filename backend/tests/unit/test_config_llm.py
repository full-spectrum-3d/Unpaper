from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**kw: Any) -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None, **kw)


def test_llm_defaults() -> None:
    s = _settings()
    assert (s.llm_timeout_s, s.request_timeout_s, s.llm_default_mode) == (240, 540, "accurate")
    assert s.llm_model_for("accurate") == "qwen3:8b"
    assert s.llm_model_for("fast") == "qwen3:4b"


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(llm_default_mode="turbo")
