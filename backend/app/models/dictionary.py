"""Katalog słowników eUsług (spec §8.4, §8.6).

Słownik predefiniowany (`PREDEFINED`) jest dostępny w Generatorze Formularzy COI
i pole odwołuje się do niego przez `dictionaryName`. Propozycja (`PROPOSED`) to
słownik, którego jeszcze nie ma - pole dostaje opcje inline, a propozycja trafia
do raportu konwersji.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from app.core.text import to_tech_name
from app.models.form import FieldType

DictionaryStatus = Literal["PREDEFINED", "PROPOSED"]


class _CatalogModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", frozen=True
    )


class DictionaryItem(_CatalogModel):
    code: str
    name: str
    tech_name: str = ""
    valid_from: str | None = None
    valid_to: str | None = None

    @model_validator(mode="after")
    def _derive_tech_name(self) -> Self:
        if not self.tech_name:
            object.__setattr__(self, "tech_name", to_tech_name(self.name))
        return self


class DictionaryEntry(_CatalogModel):
    name: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    title: str
    description: str
    status: DictionaryStatus
    field_types: tuple[FieldType, ...] = Field(min_length=1)
    multi_level_tree: bool = False
    default_value: tuple[str, ...] = ()
    item_structure: tuple[str, ...]
    # Wyrażenia regularne na znormalizowanej etykiecie pola (małe litery, pojedyncze spacje).
    label_patterns: tuple[str, ...] = ()
    items: tuple[DictionaryItem, ...] = ()


class DictionaryCatalog(_CatalogModel):
    dictionaries: tuple[DictionaryEntry, ...]
    proposals: tuple[DictionaryEntry, ...]


class DictionaryProposal(_CatalogModel):
    """Propozycja nowego słownika w raporcie (`report.dictionaryProposals`)."""

    name: str
    title: str
    description: str
    item_structure: tuple[str, ...]
    items: tuple[DictionaryItem, ...]
    used_by: tuple[str, ...]
