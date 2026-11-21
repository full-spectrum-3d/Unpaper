"""Mapowanie pól szkicu na pola COI: typy, walidatory, techName, słowniki (spec §7.2, §8.3, §8.4).

`FieldBuilder` przechodzi po polach szkicu (`DraftField`) i zwraca gotowe `Field`.
Układ siatki (`Question`) robi `layout.py`, a warunki widoczności (`states`)
`states.py` - korzysta z map `draft_ids` i `produced`.
"""

import html
import re
import uuid
from collections.abc import Callable

from app.core.text import to_tech_name
from app.models.draft import DraftField, DraftSection
from app.models.form import Field, FieldType, Option, Validator
from app.models.warning import ConversionWarning
from app.pipeline.build.dictionaries import (
    bind_dictionary,
    is_phone_field,
    normalize_label,
    phone_prefix_field,
)

MAX_RADIO_OPTIONS = 5
SEARCH_ENABLED_MIN_OPTIONS = 16
MAX_LABEL_LENGTH = 80
DEFAULT_TECH_NAME = "pole"

_SIMPLE_TYPES: dict[str, FieldType] = {
    "short_text": FieldType.TEXT_FIELD,
    "long_text": FieldType.TEXTAREA,
    "number": FieldType.NUMBER,
    "date": FieldType.DATEPICKER,
    "multi_choice": FieldType.CHECKBOX,
    "file": FieldType.FILE_UPLOADER,
    "info": FieldType.TEXT_BLOCK,
}

# Walidatory formatu po etykiecie (spec §8.3). Kolejność nie ma znaczenia:
# gdy pasuje więcej niż jeden (np. „PESEL lub NIP”), nie ustawiamy żadnego.
_FORMAT_VALIDATORS: tuple[tuple[Validator, re.Pattern[str]], ...] = (
    (Validator.PESEL, re.compile(r"\bpesel\b")),
    (Validator.NIP, re.compile(r"\bnip\b")),
    (Validator.REGON, re.compile(r"\bregon\b")),
    (Validator.ZIP_CODE, re.compile(r"\bkod pocztowy\b")),
    (Validator.EMAIL, re.compile(r"\be-?mail\b|\badres poczty elektronicznej\b")),
    (Validator.EPUAP, re.compile(r"\bepuap\b|\bskrytk")),
    (Validator.ADE, re.compile(r"\be-?doręcze")),
    (
        Validator.SERIAL_NUMBER_ID_CARD,
        re.compile(r"\bseri\w* i numer dowodu\b|\bnumer dowodu osobistego\b"),
    ),
)
# Typy, w których wolno użyć walidatora formatu (R15). Pozostałe: tylko REQUIRED.
_FORMAT_FIELD_TYPES = frozenset({FieldType.TEXT_FIELD})
_NO_VALIDATION_TYPES = frozenset({FieldType.TEXT_BLOCK})
_CHOICE_TYPES = frozenset({FieldType.RADIO, FieldType.SELECT, FieldType.CHECKBOX})

IdFactory = Callable[[], str]


def _uuid4() -> str:
    return str(uuid.uuid4())


class FieldBuilder:
    """Buduje pola jednego formularza; pilnuje unikalności `techName` (R12)."""

    def __init__(self, id_factory: IdFactory = _uuid4) -> None:
        self._new_id = id_factory
        self._tech_names: set[str] = set()
        # id pola szkicu → techName pola głównego (cel warunków `visible_when`).
        self.draft_ids: dict[str, str] = {}
        # id pola szkicu → techName wszystkich pól z niego zbudowanych (komu dać `states`).
        self.produced: dict[str, list[str]] = {}
        self.warnings: list[ConversionWarning] = []

    def reserve_tech_name(self, base: str) -> str:
        """Unikalny techName: `kraj`, potem `kraj_2`, `kraj_3`… (spec §5, naprawy)."""
        base = base or DEFAULT_TECH_NAME
        name, n = base, 1
        while name in self._tech_names:
            n += 1
            name = f"{base}_{n}"
        self._tech_names.add(name)
        return name

    def build_section_fields(self, section: DraftSection, path: str) -> list[Field]:
        """Pola sekcji w kolejności szkicu, z `questionOrder` = pozycja w sekcji."""
        fields: list[Field] = []
        for k, draft in enumerate(section.fields):
            fields.extend(self.build_field(draft, f"{path}.fields[{k}]"))
        return [f.model_copy(update={"question_order": i}) for i, f in enumerate(fields)]

    def build_field(self, draft: DraftField, path: str) -> list[Field]:
        """Jedno pole szkicu → 1 pole COI (albo 2: numer kierunkowy + telefon)."""
        field_type = _field_type(draft)
        format_validator = _format_validator(draft.label)
        if format_validator and field_type is FieldType.NUMBER:
            # PESEL/NIP/kod jako liczba gubi zera wiodące i walidator formatu.
            field_type = FieldType.TEXT_FIELD

        tech_name = self.reserve_tech_name(to_tech_name(draft.label))
        self.draft_ids[draft.id] = tech_name
        field = Field(
            id=self._new_id(),
            type=field_type,
            tech_name=tech_name,
            title="" if field_type is FieldType.TEXT_BLOCK else draft.label,
            description=_text_block_html(draft.label) if field_type is FieldType.TEXT_BLOCK else "",
            options=_options(draft.options) if field_type in _CHOICE_TYPES else [],
            validation=_validation(draft.required, field_type, format_validator),
        )
        if field_type is FieldType.SELECT and len(field.options) >= SEARCH_ENABLED_MIN_OPTIONS:
            field = field.model_copy(update={"search_enabled": True})

        field, dictionary_warnings = bind_dictionary(field, path)
        self.warnings.extend(dictionary_warnings)
        self._check_label(draft.label, path)

        if is_phone_field(field):
            prefix = phone_prefix_field(field, field_id=self._new_id())
            prefix = prefix.model_copy(
                update={"tech_name": self.reserve_tech_name(prefix.tech_name)}
            )
            self.produced[draft.id] = [prefix.tech_name, field.tech_name]
            return [prefix, field]
        self.produced[draft.id] = [field.tech_name]
        return [field]

    def _check_label(self, label: str, path: str) -> None:
        if len(label) > MAX_LABEL_LENGTH:
            self.warnings.append(
                ConversionWarning(
                    code="W22_LABEL_TOO_LONG",
                    message=(
                        f"Etykieta ma {len(label)} znaków (zalecane ≤ {MAX_LABEL_LENGTH}). "
                        "Przenieś wyjaśnienia do opisu pola."
                    ),
                    path=path,
                )
            )


def _field_type(draft: DraftField) -> FieldType:
    if draft.kind == "single_choice":
        return FieldType.RADIO if len(draft.options) <= MAX_RADIO_OPTIONS else FieldType.SELECT
    return _SIMPLE_TYPES[draft.kind]


def _format_validator(label: str) -> Validator | None:
    text = normalize_label(label)
    found = [v for v, pattern in _FORMAT_VALIDATORS if pattern.search(text)]
    return found[0] if len(found) == 1 else None


def _validation(
    required: bool, field_type: FieldType, format_validator: Validator | None
) -> list[Validator]:
    if field_type in _NO_VALIDATION_TYPES:
        return []
    out = [Validator.REQUIRED] if required else []
    if format_validator and field_type in _FORMAT_FIELD_TYPES:
        out.append(format_validator)
    return out


def _options(names: list[str]) -> list[Option]:
    """`id` = `name` jak we wzorcach (spec §7.2); duplikaty pomijamy."""
    out: list[Option] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(Option(id=name, name=name, tech_name=to_tech_name(name)))
    return out


def _text_block_html(text: str) -> str:
    return f"<html><head></head><body><p>{html.escape(text)}</p></body></html>"
