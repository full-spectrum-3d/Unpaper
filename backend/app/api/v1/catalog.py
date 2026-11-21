"""GET /dictionaries, GET /initial-data-sources (spec §6.1, §8.4-8.6)."""

from fastapi import APIRouter

router = APIRouter(tags=["catalog"])


@router.get("/dictionaries")
async def list_dictionaries() -> list[dict[str, object]]:
    raise NotImplementedError


@router.get("/initial-data-sources")
async def list_initial_data_sources() -> list[dict[str, object]]:
    raise NotImplementedError
