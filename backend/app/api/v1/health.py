"""/health/live, /health/ready (spec §6.1)."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    # TODO: sprawdzić osiągalność LLM i załadowanie modelu → 503 gdy niegotowe
    raise NotImplementedError
