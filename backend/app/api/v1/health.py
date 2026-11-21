"""/health/live, /health/ready (spec §6.1, projekt LLM §5.6-5.7)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.pipeline.converter import Converter, get_converter
from app.pipeline.llm_client import LlmClient, LlmError, get_llm_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[LlmClient, Depends(get_llm_client)],
    converter: Annotated[Converter | None, Depends(get_converter)],
) -> dict[str, object]:
    """Gotowość: serwer modelu osiągalny i model pobrany.

    `degraded` wymienia `converter`, gdy w obrazie nie ma
    LibreOffice (wtedy DOC/ODS dostają 415, reszta formatów działa).
    """
    try:
        models = await client.list_models()
    except LlmError as exc:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, str(exc)) from exc

    if settings.llm_model not in models:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, f"brak modelu {settings.llm_model}")
    if converter is None:
        return {"status": "ok", "degraded": ["converter"]}
    return {"status": "ok"}
