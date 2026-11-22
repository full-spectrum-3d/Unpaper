"""GET /dictionaries, GET /dictionaries/teryt, GET /initial-data-sources (spec §6.1, §8.4-8.6)."""

import gzip
from typing import Any

from fastapi import APIRouter, Header, Response

from app.pipeline.build.catalogs import (
    load_dictionary_catalog,
    load_initial_data_catalog,
    load_teryt_gzip,
)
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


@router.get(
    "/dictionaries/teryt",
    responses={200: {"content": {"application/json": {}}, "description": "Pełne drzewo TERYT"}},
)
async def teryt_tree(accept_encoding: str = Header(default="")) -> Response:
    """Pozycje słowników TERYT: `{asOf, levels, items}` z węzłami `{name, code?, children?}`.

    Plik leży w gzip (ok. 0,3 MB zamiast 1,5 MB) i tak jest wysyłany, gdy klient to akceptuje.
    """
    body = load_teryt_gzip()
    headers = {"Cache-Control": "private, max-age=86400", "Vary": "Accept-Encoding"}
    if "gzip" in accept_encoding.lower():
        return Response(
            body, media_type="application/json", headers=headers | {"Content-Encoding": "gzip"}
        )
    return Response(gzip.decompress(body), media_type="application/json", headers=headers)


_SOURCE_NAMES = {
    "PESEL": "Rejestr PESEL",
    "PESEL_ADDRESS": "Dane zameldowania",
    "MLPZ": "Dane zalogowanego użytkownika",
}


@router.get("/initial-data-sources")
async def list_initial_data_sources() -> list[dict[str, Any]]:
    """Źródła danych inicjalnych z atrybutami (spec §8.5). `ref` trafia do `defaultValue`."""
    sources: dict[str, dict[str, Any]] = {}
    for attr in load_initial_data_catalog().values():
        source = sources.setdefault(
            attr.source,
            {
                "source": attr.source,
                "name": _SOURCE_NAMES.get(attr.source, attr.source),
                "attributes": [],
            },
        )
        source["attributes"].append(
            {
                "attribute": attr.attribute,
                "ref": attr.ref,
                "label": attr.label,
                "fieldType": attr.field_type,
                "editable": attr.editable,
            }
        )
    return list(sources.values())
