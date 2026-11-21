"""FormDefinition - wynik końcowy w formacie importu COI (spec §7.1, projekt LLM §5.3).

Odwzorowuje wzorcowe `konfiguracja_form_*.json` (nie schemat, por. spec §7.4).
Klucze bazowe pola (spec §7.2) są zawsze serializowane, klucze dodatkowe tylko
gdy są ustawione. Model sprawdza wyłącznie typy - reguły R01-R15 są w `verify.py`.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel


class _CoiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class FieldType(StrEnum):
    TEXT_FIELD = "TEXT_FIELD"
    TEXTAREA = "TEXTAREA"
    NUMBER = "NUMBER"
    DATEPICKER = "DATEPICKER"
    RADIO = "RADIO"
    SELECT = "SELECT"
    CHECKBOX = "CHECKBOX"
    FILE_UPLOADER = "FILE_UPLOADER"
    TEXT_BLOCK = "TEXT_BLOCK"
    SECTION = "SECTION"
    REPEATING_SECTION = "REPEATING_SECTION"
    CONSENT_SECTION = "CONSENT_SECTION"
    INFO_SECTION = "INFO_SECTION"


class Validator(StrEnum):
    REQUIRED = "REQUIRED"
    EMAIL = "EMAIL"
    PESEL = "PESEL"
    NIP = "NIP"
    REGON = "REGON"
    ZIP_CODE = "ZIP_CODE"
    EPUAP = "EPUAP"
    ADE = "ADE"
    SERIAL_NUMBER_ID_CARD = "SERIAL_NUMBER_ID_CARD"


class Option(_CoiModel):
    id: str
    name: str
    tech_name: str


class State(_CoiModel):
    type: Literal["SHOW", "READ_ONLY"]
    query: str


class Consent(_CoiModel):
    description: str
    required: bool | None = None


class ConsentSectionConfig(_CoiModel):
    consents: list[Consent]
    required: bool | None = None
    files: list[dict[str, Any]] = []


class Field(_CoiModel):
    # Klucze bazowe - zawsze w wyniku.
    id: str
    type: FieldType
    tech_name: str
    title: str = ""
    description: str = ""
    options: list[Option] = []
    validation: list[Validator] = []
    read_only: bool = False
    repeating_section_grid: list[Question] = []
    states: list[State] = []
    question_order: int = 0
    tooltip_message: str = ""
    # Klucze dodatkowe - tylko gdy ustawione.
    default_value: str | list[str] | None = None
    default_value_type: Literal["EXTERNAL_SYSTEM"] | None = None
    dictionary_name: str | None = None
    search_enabled: bool | None = None
    multi_level_tree: bool | None = None
    consent_section_config: ConsentSectionConfig | None = None
    select_all_enabled: bool | None = None

    @field_validator("validation", mode="before")
    @classmethod
    def _empty_object_is_empty_list(cls, value: object) -> object:
        # Wzorce COI zawierają czasem `"validation": {}` zamiast pustej listy.
        return [] if value == {} else value


class Question(_CoiModel):
    x: int
    y: int
    rows: int
    cols: int
    min_item_rows: int | None = None
    field: Field


class Tab(_CoiModel):
    id: str
    title: str
    type: Literal["MAIN", "FINISH"]
    questions: list[Question]


class FlowLink(_CoiModel):
    id: str
    source: str
    target: str


class Flow(_CoiModel):
    links: list[FlowLink]


class FormDefinition(_CoiModel):
    title: str
    tabs: list[Tab]
    flow: Flow

    def to_import_json(self) -> dict[str, Any]:
        """JSON zwracany przez API: camelCase, bez nieustawionych kluczy dodatkowych."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")
