"""Pośrednia reprezentacja formularza przed serializacją (spec §8)."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from app.models.form import FieldType, TabType, Validator


class Semantic(StrEnum):
    """Znaczenie pola ustalone z etykiety (walidatory i słowniki)."""

    PESEL = "PESEL"
    NIP = "NIP"
    REGON = "REGON"
    ZIP_CODE = "ZIP_CODE"
    EMAIL = "EMAIL"
    EPUAP = "EPUAP"
    ADE = "ADE"
    ID_CARD = "ID_CARD"
    COUNTRY = "COUNTRY"
    PHONE_PREFIX = "PHONE_PREFIX"


@dataclass(frozen=True)
class Eq:
    ref: str
    value: str


@dataclass(frozen=True)
class Not:
    cond: Condition


@dataclass(frozen=True)
class AllOf:
    items: tuple[Condition, ...]


@dataclass(frozen=True)
class AnyOf:
    items: tuple[Condition, ...]


type Condition = Eq | Not | AllOf | AnyOf


@dataclass
class Consent:
    description_html: str
    required: bool


@dataclass
class FieldNode:
    key: str
    type: FieldType
    title: str
    tech_name: str
    description_html: str = ""
    tooltip: str = ""
    options: list[str] = field(default_factory=list)
    validation: list[Validator] = field(default_factory=list)
    read_only: bool = False
    dictionary_name: str | None = None
    search_enabled: bool | None = None
    multi_level_tree: bool | None = None
    default_value: str | list[str] | None = None
    default_value_type: str | None = None
    initial_data: str | None = None
    consents: list[Consent] = field(default_factory=list)
    select_all_enabled: bool | None = None
    semantic: Semantic | None = None
    show_when: Condition | None = None
    read_only_when: Condition | None = None


@dataclass
class SectionNode:
    key: str
    type: FieldType
    title: str
    tech_name: str
    description_html: str = ""
    fields: list[FieldNode] = field(default_factory=list)
    show_when: Condition | None = None


@dataclass
class PageNode:
    key: str
    title: str
    type: TabType
    sections: list[SectionNode] = field(default_factory=list)


def iter_fields(pages: list[PageNode]) -> Iterator[tuple[PageNode, SectionNode, FieldNode]]:
    for page in pages:
        for section in page.sections:
            for node in section.fields:
                yield page, section, node
