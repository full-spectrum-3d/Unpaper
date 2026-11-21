"""POST /forms/convert, POST /forms/validate (spec §6.1-6.3)."""

from fastapi import APIRouter

from app.core.config import LlmMode

router = APIRouter(prefix="/forms", tags=["forms"])


@router.post("/convert")
async def convert(report: bool = False, mode: LlmMode | None = None) -> dict[str, object]:
    """Główny endpoint: 1 plik → JSON w formacie importu (lub {form, report}).

    `mode`: tryb analizy LLM (`accurate`/`fast`), domyślnie `LLM_DEFAULT_MODE`.
    """
    raise NotImplementedError


@router.post("/validate")
async def validate() -> dict[str, object]:
    """Walidacja dowolnego JSON-a formularza → {valid, errors[], warnings[]}."""
    raise NotImplementedError
