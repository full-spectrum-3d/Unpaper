"""FormDefinition - wynik końcowy w formacie importu COI (spec §7.1, projekt LLM §5.3).

Format wyznacza `wymagania/OpisImportowanegoPlikuJSON.md`. Literówki dokumentu traktujemy
jako błędy w dokumencie: siatka sekcji to `repeatingSectionGrid` (dokument i schemat piszą
`repetingSectionGrid`), opis zgody to `description` (dokument pisze `descripton`).
Klucze spoza dokumentu nie są emitowane; starsze formularze (wzorce `konfiguracja_form_*.json`)
oraz JSON-y z kluczem z literówką tłumaczy `to_document_format`.
Klucze bazowe pola (spec §7.2) są zawsze serializowane, klucze dodatkowe tylko
gdy są ustawione. Model sprawdza wyłącznie typy - reguły R01-R15 są w `verify.py`.
"""

import copy
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


# --- Stałe reguł (spec §7.2-7.3), wspólne dla `build/` i `verify.py` ---

SECTION_TYPES: frozenset[FieldType] = frozenset({FieldType.SECTION, FieldType.REPEATING_SECTION})
INPUT_TYPES: frozenset[FieldType] = (
    frozenset(FieldType) - SECTION_TYPES - {FieldType.TEXT_BLOCK, FieldType.INFO_SECTION}
)
CHOICE_TYPES: frozenset[FieldType] = frozenset(
    {FieldType.SELECT, FieldType.RADIO, FieldType.CHECKBOX}
)

_REQUIRED_ONLY = frozenset({Validator.REQUIRED})
ALLOWED_VALIDATORS: dict[FieldType, frozenset[Validator]] = {
    FieldType.TEXT_FIELD: frozenset(Validator),
    FieldType.TEXTAREA: _REQUIRED_ONLY,
    FieldType.NUMBER: _REQUIRED_ONLY,
    FieldType.SELECT: _REQUIRED_ONLY,
    FieldType.RADIO: _REQUIRED_ONLY,
    FieldType.CHECKBOX: _REQUIRED_ONLY,
    FieldType.DATEPICKER: _REQUIRED_ONLY,
    FieldType.FILE_UPLOADER: _REQUIRED_ONLY,
    FieldType.TEXT_BLOCK: frozenset(),
    FieldType.INFO_SECTION: frozenset(),
    FieldType.CONSENT_SECTION: frozenset(),
    FieldType.SECTION: frozenset(),
    FieldType.REPEATING_SECTION: frozenset(),
}


class TabType(StrEnum):
    MAIN = "MAIN"
    FINISH = "FINISH"


class StateType(StrEnum):
    SHOW = "SHOW"
    READ_ONLY = "READ_ONLY"


EXTERNAL_SYSTEM = "EXTERNAL_SYSTEM"

BASE_FIELD_KEYS: tuple[str, ...] = (
    "id",
    "type",
    "techName",
    "title",
    "description",
    "options",
    "validation",
    "readOnly",
    "repeatingSectionGrid",
    "states",
    "questionOrder",
    "tooltipMessage",
)

EMPTY_HTML = "<html><head></head><body></body></html>"

type FormJson = dict[str, Any]
"""Formularz jako surowy JSON importu (wynik `to_import_json()`, wejście `verify_form`)."""


class Option(_CoiModel):
    id: str
    name: str
    tech_name: str


class State(_CoiModel):
    type: Literal["SHOW", "READ_ONLY"]
    query: str


class Consent(_CoiModel):
    description: str


class ConsentSectionConfig(_CoiModel):
    consents: list[Consent]
    required: bool
    files: list[str] = []


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
    default_value: str | None = None
    default_value_type: Literal["EXTERNAL_SYSTEM"] | None = None
    dictionary_name: str | None = None
    consent_section_config: ConsentSectionConfig | None = None

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


# --- Tłumaczenie starszego formatu (wzorce COI) na format z dokumentu ---

# Pisownia z dokumentu i schematu importu (literówka) - przyjmowana na wejściu.
LEGACY_GRID_KEY = "repetingSectionGrid"
GRID_KEY = "repeatingSectionGrid"
DROPPED_FIELD_KEYS: tuple[str, ...] = ("searchEnabled", "multiLevelTree", "selectAllEnabled")
DROPPED_QUESTION_KEYS: tuple[str, ...] = ("minItemRows",)


def default_value_string(value: object) -> object:
    """`defaultValue` jako string (dokument): lista wzorca -> pierwszy element, pusta -> brak."""
    if isinstance(value, list):
        items = [v for v in value if isinstance(v, str)]
        return items[0] if items else None
    return value


def _rename_key(node: dict[str, Any], old: str, new: str) -> None:
    """Zmienia nazwę klucza w miejscu, zachowując kolejność (czytelny diff JSON-a)."""
    items = [(new if k == old else k, v) for k, v in node.items() if not (k == new and old in node)]
    node.clear()
    node.update(items)


def _legacy_consents(config: dict[str, Any], changes: list[str], path: str) -> None:
    consents = config.get("consents")
    if not isinstance(consents, list):
        return
    flags: list[bool] = []
    for consent in consents:
        if not isinstance(consent, dict):
            continue
        if "required" in consent:
            flag = consent.pop("required")
            flags.append(flag is True)
            changes.append(f"{path}.consents: required -> consentSectionConfig.required")
    if "required" not in config and flags:
        config["required"] = any(flags)
    files = config.get("files")
    if isinstance(files, list) and any(not isinstance(f, str) for f in files):
        config["files"] = [f["name"] for f in files if isinstance(f, dict) and "name" in f]
        changes.append(f"{path}.files: tylko nazwy plików")


def _legacy_field(field: dict[str, Any], changes: list[str], path: str) -> None:
    if LEGACY_GRID_KEY in field:
        _rename_key(field, LEGACY_GRID_KEY, GRID_KEY)
        changes.append(f"{path}: {LEGACY_GRID_KEY} -> {GRID_KEY}")
    states = field.get("states")
    for state in states if isinstance(states, list) else ():
        query = state.get("query") if isinstance(state, dict) else None
        if isinstance(query, str) and LEGACY_GRID_KEY in query:
            state["query"] = query.replace(LEGACY_GRID_KEY, GRID_KEY)
            changes.append(f"{path}.states: ścieżka {LEGACY_GRID_KEY} -> {GRID_KEY}")
    for key in DROPPED_FIELD_KEYS:
        if key in field:
            del field[key]
            changes.append(f"{path}: usunięto {key}")
    if field.get("validation") == {}:
        field["validation"] = []
        changes.append(f"{path}: validation {{}} -> []")
    if isinstance(field.get("defaultValue"), list):
        value = default_value_string(field["defaultValue"])
        if value is None:
            del field["defaultValue"]
        else:
            field["defaultValue"] = value
        changes.append(f"{path}: defaultValue jako string")
    config = field.get("consentSectionConfig")
    if isinstance(config, dict):
        _legacy_consents(config, changes, f"{path}.consentSectionConfig")
    _legacy_questions(field.get(GRID_KEY), changes, f"{path}.{GRID_KEY}")


def _legacy_questions(questions: object, changes: list[str], path: str) -> None:
    if not isinstance(questions, list):
        return
    for i, question in enumerate(questions):
        if not isinstance(question, dict):
            continue
        for key in DROPPED_QUESTION_KEYS:
            if key in question:
                del question[key]
                changes.append(f"{path}[{i}]: usunięto {key}")
        field = question.get("field")
        if isinstance(field, dict):
            _legacy_field(field, changes, f"{path}[{i}].field")


def to_document_format(form: Any) -> tuple[Any, list[str]]:
    """Kopia formularza w formacie z dokumentu oraz lista wprowadzonych zmian.

    Nie zmienia formularza już zgodnego z dokumentem (lista zmian jest wtedy pusta).
    """
    if not isinstance(form, dict):
        return form, []
    result = copy.deepcopy(form)
    changes: list[str] = []
    tabs = result.get("tabs")
    if isinstance(tabs, list):
        for i, tab in enumerate(tabs):
            if isinstance(tab, dict):
                _legacy_questions(tab.get("questions"), changes, f"tabs[{i}].questions")
    return result, changes
