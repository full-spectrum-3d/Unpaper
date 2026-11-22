"""Katalogi słowników, danych inicjalnych i schemat importu (spec §7, §8)."""

import json
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

from app.models.form import FieldType
from app.pipeline.build.ir import Semantic


@dataclass(frozen=True)
class DictionaryEntry:
    name: str
    description: str
    field_types: tuple[FieldType, ...]
    multi_level_tree: bool
    semantics: frozenset[Semantic]


@dataclass(frozen=True)
class InitialDataAttribute:
    source: str
    attribute: str
    label: str
    field_type: FieldType
    editable: bool

    @property
    def ref(self) -> str:
        return f"{self.source}.{self.attribute}"


def _load_json(*parts: str) -> Any:
    resource = files("app.resources").joinpath(*parts)
    return json.loads(resource.read_text(encoding="utf-8"))


@cache
def load_dictionary_catalog() -> dict[str, DictionaryEntry]:
    entries = (
        DictionaryEntry(
            name=item["name"],
            description=item["description"],
            field_types=tuple(FieldType(t) for t in item["fieldTypes"]),
            multi_level_tree=item["multiLevelTree"],
            semantics=frozenset(Semantic(s) for s in item["semantics"]),
        )
        for item in _load_json("dictionaries.json")
    )
    return {entry.name: entry for entry in entries}


@cache
def load_initial_data_catalog() -> dict[str, InitialDataAttribute]:
    attributes = (
        InitialDataAttribute(
            source=item["source"],
            attribute=item["attribute"],
            label=item["label"],
            field_type=FieldType(item["fieldType"]),
            editable=item["editable"],
        )
        for item in _load_json("initial_data.json")
    )
    return {attr.ref: attr for attr in attributes}


@cache
def load_teryt_gzip() -> bytes:
    """Drzewo TERYT (województwo → powiat → gmina → miejscowość) jako gotowy JSON w gzip.

    Generowane skryptem `scripts/build_teryt.py` z urzędowych plików TERC i SIMC (GUS).
    """
    return files("app.resources").joinpath("teryt.json.gz").read_bytes()


@cache
def load_form_schema() -> dict[str, Any]:
    schema: dict[str, Any] = _load_json("schema", "importowanyPlikJsonSchemat.json")
    return schema
