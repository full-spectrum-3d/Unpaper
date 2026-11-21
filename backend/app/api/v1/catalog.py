"""GET /dictionaries, GET /initial-data-sources (spec §6.1, §8.4-8.6)."""

from typing import Any

from fastapi import APIRouter

from app.pipeline.build.dictionaries import catalog_listing

router = APIRouter(tags=["catalog"])


@router.get("/dictionaries")
async def list_dictionaries() -> list[dict[str, Any]]:
    """Słowniki predefiniowane (`PREDEFINED`) i proponowane (`PROPOSED`, z pozycjami)."""
    return catalog_listing()


@router.get("/initial-data-sources")
async def list_initial_data_sources() -> list[dict[str, object]]:
    raise NotImplementedError
