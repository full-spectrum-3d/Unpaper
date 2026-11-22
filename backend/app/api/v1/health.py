"""/health/live, /health/ready (spec §6.1, projekt LLM §5.6-5.7)."""

import logging
import shutil
from typing import Annotated, Literal

import pytesseract
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.openapi import problem_responses
from app.pipeline.converter import Converter, get_converter
from app.pipeline.llm_client import LlmClient, LlmError, get_llm_client

router = APIRouter(prefix="/health", tags=["health"])

logger = logging.getLogger(__name__)


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ok"] = "ok"
    degraded: list[Literal["converter"]] | None = Field(
        default=None,
        description="Działające z ograniczeniami części; `converter`: brak LibreOffice, "
        "pliki DOC i ODS dostają 415",
    )


def missing_tools() -> list[str]:
    """Zależności systemowe, bez których każda konwersja kończy się błędem 500.

    Osobna zależność FastAPI, żeby testy mogły ją podmienić (`dependency_overrides`).
    """
    missing = []
    try:
        import magic  # noqa: F401 - leniwie jak w upload_validation.mime
    except ImportError:
        missing.append("libmagic")
    if shutil.which(pytesseract.pytesseract.tesseract_cmd) is None:
        missing.append("tesseract")
    return missing


def _tag(model: str) -> str:
    """Ollama traktuje nazwę bez tagu jak `:latest` (`qwen3` == `qwen3:latest`)."""
    return model if ":" in model.rsplit("/", 1)[-1] else f"{model}:latest"


@router.get("/live", summary="Liveness")
async def live() -> LiveResponse:
    """Proces odpowiada. Nie sprawdza zależności."""
    return LiveResponse()


@router.get(
    "/ready",
    response_model_exclude_none=True,
    summary="Readiness",
    responses=problem_responses(
        ErrorCode.LLM_UNAVAILABLE, ErrorCode.SERVICE_UNAVAILABLE, instance="/api/v1/health/ready"
    ),
)
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[LlmClient, Depends(get_llm_client)],
    converter: Annotated[Converter | None, Depends(get_converter)],
    missing: Annotated[list[str], Depends(missing_tools)],
) -> ReadyResponse:
    """Gotowość: serwer modelu osiągalny i model pobrany.

    `degraded` wymienia `converter`, gdy w obrazie nie ma
    LibreOffice (wtedy DOC/ODS dostają 415, reszta formatów działa).
    """
    if missing:
        logger.error("brak zależności systemowych: %s", ", ".join(missing))
        raise AppError(ErrorCode.SERVICE_UNAVAILABLE)
    try:
        models = await client.list_models()
    except LlmError as exc:
        # Szczegóły (adres, treść odpowiedzi) tylko w logach - endpoint jest publiczny.
        logger.warning("serwer modelu niedostępny: %s", exc)
        raise AppError(ErrorCode.LLM_UNAVAILABLE) from exc

    if _tag(settings.llm_model) not in {_tag(m) for m in models}:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, f"brak modelu {settings.llm_model}")
    if converter is None:
        return ReadyResponse(degraded=["converter"])
    return ReadyResponse()
