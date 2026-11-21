"""GET /dictionaries, GET /initial-data-sources (spec §6.1, §8.4-8.6)."""

from typing import Any

from fastapi import APIRouter

from app.pipeline.build.catalogs import load_dictionary_catalog
from app.pipeline.build.proposals import load_proposal_catalog

router = APIRouter(tags=["catalog"])


@router.get("/dictionaries")
async def list_dictionaries() -> list[dict[str, Any]]:
    """Słowniki predefiniowane (`PREDEFINED`), potem proponowane (`PROPOSED`, z pozycjami)."""
    predefined = [
        {
            "name": entry.name,
            "description": entry.description,
            "status": "PREDEFINED",
            "fieldTypes": list(entry.field_types),
            "multiLevelTree": entry.multi_level_tree,
        }
        for entry in load_dictionary_catalog().values()
    ]
    proposed = [template.to_catalog_json() for template in load_proposal_catalog()]
    return predefined + proposed


@router.get("/initial-data-sources")
async def list_initial_data_sources() -> list[dict[str, object]]:
    raise NotImplementedError
