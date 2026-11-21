"""/health/live, /health/ready (spec §6.1, projekt LLM §5.6-5.7)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode, problem_doc
from app.pipeline.converter import Converter, get_converter
from app.pipeline.llm_client import LlmClient, LlmError, get_llm_client

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ok"] = "ok"
    degraded: list[Literal["converter"]] | None = Field(
        default=None,
        description="Działające z ograniczeniami części; `converter`: brak LibreOffice, "
        "pliki DOC i ODS dostają 415",
    )


@router.get("/live")
async def live() -> LiveResponse:
    return LiveResponse()


@router.get(
    "/ready",
    response_model_exclude_none=True,
    responses={503: problem_doc("LLM_UNAVAILABLE: serwer modelu nieosiągalny albo brak modelu")},
)
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[LlmClient, Depends(get_llm_client)],
    converter: Annotated[Converter | None, Depends(get_converter)],
) -> ReadyResponse:
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
        return ReadyResponse(degraded=["converter"])
    return ReadyResponse()
