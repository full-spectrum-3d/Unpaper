"""Powiązania ze słownikami + propozycje nowych (spec §8.4, §8.6).

Pole wyboru, którego etykieta wskazuje dane standaryzowane (kraj, województwo,
powiat, gmina, miejscowość, numer kierunkowy), dostaje `dictionaryName`,
`options: []` i `searchEnabled: true` - użytkownik wybiera pozycję zamiast
wpisywać tekst. Słowniki z katalogu wolno podpiąć tylko pod `SELECT`, więc
`TEXT_FIELD` i `RADIO` zamieniamy na `SELECT`, a `CHECKBOX` (wielokrotny wybór)
zostawiamy z ostrzeżeniem.

Pole, dla którego słownika brakuje, a lista ma charakter zamknięty i ogólnokrajowy
(rodzaj podatku, rodzaj dokumentu tożsamości...), zachowuje opcje inline, a propozycja słownika
trafia do raportu.
"""

import json
import re
import uuid
from collections.abc import Iterable, Iterator
from functools import cache
from importlib.resources import files
from typing import Any

from app.core.text import to_tech_name
from app.models.dictionary import (
    DictionaryCatalog,
    DictionaryEntry,
    DictionaryItem,
    DictionaryProposal,
)
from app.models.form import Field, FieldType, Option, Validator
from app.models.warning import ConversionWarning

PHONE_PREFIX_DICTIONARY = "NUMERY_KIERUNKOWE"
DICTIONARY_FIELD_TYPES = frozenset({FieldType.SELECT, FieldType.RADIO, FieldType.CHECKBOX})
# Typy, które da się bez utraty znaczenia zamienić na SELECT ze słownikiem.
_CONVERTIBLE_TO_SELECT = frozenset({FieldType.TEXT_FIELD, FieldType.RADIO})
# Pola, w których szukamy słownika: wybór albo tekst wpisywany zamiast wyboru.
_CANDIDATE_FIELD_TYPES = DICTIONARY_FIELD_TYPES | {FieldType.TEXT_FIELD}
# Minimalne pokrycie opcji pola pozycjami propozycji, żeby uznać listę za tę samą.
_MIN_OPTION_OVERLAP = 2
_OPTION_OVERLAP_RATIO = 0.5

_PHONE_LABEL = re.compile(r"^(numer )?telefonu?( (kontaktow|komórkow|stacjonarn)(y|ego))?$")
_LABEL_NOISE = re.compile(r"\(\s*(opcjonalnie|wymagane|nieobowiązkowe)\s*\)|[*:]")
_WHITESPACE = re.compile(r"\s+")


@cache
def load_catalog() -> DictionaryCatalog:
    """Katalog z `app/resources/dictionaries.json` (wczytany raz na proces)."""
    raw = (files("app") / "resources" / "dictionaries.json").read_text(encoding="utf-8")
    catalog = DictionaryCatalog.model_validate(json.loads(raw))
    for entry in (*catalog.dictionaries, *catalog.proposals):
        for pattern in entry.label_patterns:
            re.compile(pattern)  # błędny wzorzec ma wywrócić start, nie konwersję
    return catalog


def catalog_listing() -> list[dict[str, Any]]:
    """Odpowiedź `GET /dictionaries`: predefiniowane, potem proponowane."""
    catalog = load_catalog()
    return [
        entry.model_dump(by_alias=True, exclude={"label_patterns"}, mode="json")
        for entry in (*catalog.dictionaries, *catalog.proposals)
    ]


def normalize_label(label: str) -> str:
    """Etykieta do porównań: małe litery, bez `*`, `:` i dopisków `(opcjonalnie)`."""
    text = _LABEL_NOISE.sub(" ", label.casefold())
    return _WHITESPACE.sub(" ", text).strip()


def find_dictionary(name: str) -> DictionaryEntry | None:
    """Słownik predefiniowany o podanej nazwie."""
    return next((d for d in load_catalog().dictionaries if d.name == name), None)


def match_dictionary(label: str) -> DictionaryEntry | None:
    """Słownik predefiniowany, którego wzorzec pasuje do całej etykiety pola."""
    return _match_label(label, load_catalog().dictionaries)


def bind_dictionary(field: Field, path: str | None = None) -> tuple[Field, list[ConversionWarning]]:
    """Podpina słownik predefiniowany pod pole, jeśli etykieta na to wskazuje.

    Nie rusza pól, które mają już słownik albo dane inicjalne (spec R10).
    """
    if field.type not in _CANDIDATE_FIELD_TYPES:
        return field, []
    if field.dictionary_name or field.default_value_type or field.read_only:
        return field, []
    entry = match_dictionary(field.title)
    if entry is None:
        return field, []
    return apply_dictionary(field, entry, path)


def apply_dictionary(
    field: Field, entry: DictionaryEntry, path: str | None = None
) -> tuple[Field, list[ConversionWarning]]:
    """Ustawia słownik w polu, zamieniając typ na dozwolony, gdy się da."""
    target_type = field.type
    warnings: list[ConversionWarning] = []
    if field.type not in entry.field_types:
        if field.type in _CONVERTIBLE_TO_SELECT and FieldType.SELECT in entry.field_types:
            target_type = FieldType.SELECT
            warnings.append(
                ConversionWarning(
                    code="W20_DICTIONARY_TYPE_CHANGED",
                    message=(
                        f"Pole „{field.title}” zmieniono z {field.type} na SELECT, "
                        f"bo słownik {entry.name} działa tylko w liście rozwijanej."
                    ),
                    path=path,
                )
            )
        else:
            return field, [
                ConversionWarning(
                    code="W21_DICTIONARY_NOT_APPLIED",
                    message=(
                        f"Pole „{field.title}” ({field.type}) pasuje do słownika {entry.name}, "
                        f"ale słownik można podpiąć tylko pod: "
                        f"{', '.join(entry.field_types)}. Zostawiono opcje z blankietu."
                    ),
                    path=path,
                )
            ]

    update: dict[str, Any] = {
        "type": target_type,
        "dictionary_name": entry.name,
        "options": [],
        "search_enabled": True,
        # R15: SELECT dopuszcza tylko REQUIRED.
        "validation": [v for v in field.validation if v is Validator.REQUIRED],
    }
    if entry.multi_level_tree:
        update["multi_level_tree"] = True
    if field.default_value is None and entry.default_value:
        update["default_value"] = list(entry.default_value)
    return field.model_copy(update=update), warnings


def is_phone_field(field: Field) -> bool:
    """Pole tekstowe na numer telefonu (wymaga obok pola numeru kierunkowego)."""
    return field.type is FieldType.TEXT_FIELD and bool(
        _PHONE_LABEL.match(normalize_label(field.title))
    )


def phone_prefix_field(phone: Field, field_id: str | None = None) -> Field:
    """Lista rozwijana ze słownikiem numerów kierunkowych dla pola telefonu.

    Dziedziczy obligatoryjność, tylko-do-odczytu i warunki widoczności telefonu,
    żeby obie kontrolki pojawiały się i znikały razem.
    """
    entry = find_dictionary(PHONE_PREFIX_DICTIONARY)
    if entry is None:  # katalog jest częścią obrazu, brak wpisu to błąd wdrożenia
        raise LookupError(f"brak słownika {PHONE_PREFIX_DICTIONARY} w katalogu")
    base = Field(
        id=field_id or str(uuid.uuid4()),
        type=FieldType.SELECT,
        tech_name=_prefix_tech_name(phone.tech_name),
        title="Numer kierunkowy",
        validation=[v for v in phone.validation if v is Validator.REQUIRED],
        read_only=phone.read_only,
        states=list(phone.states),
        question_order=phone.question_order,
    )
    field, _ = apply_dictionary(base, entry)
    return field


def propose_dictionaries(fields: Iterable[Field]) -> list[DictionaryProposal]:
    """Propozycje nowych słowników dla pól bez słownika (raport, spec §8.6).

    Pole pasuje do propozycji po etykiecie albo po opcjach (≥ 2 i ≥ połowa
    opcji pola to pozycje propozycji). Opcje z blankietu spoza propozycji
    dopisujemy na końcu listy pozycji.
    """
    proposals = load_catalog().proposals
    used_by: dict[str, list[str]] = {}
    extra_items: dict[str, list[DictionaryItem]] = {}

    for field in _walk(fields):
        if field.dictionary_name or field.type not in _CANDIDATE_FIELD_TYPES:
            continue
        entry = _match_label(field.title, proposals) or _match_options(field.options, proposals)
        if entry is None:
            continue
        names = used_by.setdefault(entry.name, [])
        if field.tech_name not in names:
            names.append(field.tech_name)
        known = {normalize_label(i.name) for i in (*entry.items, *extra_items.get(entry.name, []))}
        for option in field.options:
            if normalize_label(option.name) not in known:
                extra_items.setdefault(entry.name, []).append(_item_from_option(option))
                known.add(normalize_label(option.name))

    return [
        DictionaryProposal(
            name=entry.name,
            title=entry.title,
            description=entry.description,
            item_structure=entry.item_structure,
            items=(*entry.items, *extra_items.get(entry.name, [])),
            used_by=tuple(used_by[entry.name]),
        )
        for entry in proposals
        if entry.name in used_by
    ]


def dictionary_violations(field: Field) -> list[str]:
    """Naruszenia reguły R08 (spec §7.3) dla jednego pola - do użycia w `verify.py`."""
    if not field.dictionary_name:
        return []
    errors: list[str] = []
    if field.type not in DICTIONARY_FIELD_TYPES:
        errors.append(
            f"R08: słownik {field.dictionary_name} w polu typu {field.type} "
            "(dozwolone: SELECT, RADIO, CHECKBOX)"
        )
    if field.options:
        errors.append(f"R08: pole ze słownikiem {field.dictionary_name} ma niepuste options")
    entry = find_dictionary(field.dictionary_name)
    if entry is not None and field.type not in entry.field_types:
        errors.append(
            f"R08: słownik {entry.name} można podpiąć tylko pod: {', '.join(entry.field_types)}"
        )
    return errors


def _match_label(label: str, entries: Iterable[DictionaryEntry]) -> DictionaryEntry | None:
    text = normalize_label(label)
    if not text:
        return None
    for entry in entries:
        if any(re.match(pattern, text) for pattern in entry.label_patterns):
            return entry
    return None


def _match_options(
    options: list[Option], entries: Iterable[DictionaryEntry]
) -> DictionaryEntry | None:
    if len(options) < _MIN_OPTION_OVERLAP:
        return None
    names = {normalize_label(o.name) for o in options}
    for entry in entries:
        overlap = len(names & {normalize_label(i.name) for i in entry.items})
        if overlap >= _MIN_OPTION_OVERLAP and overlap >= _OPTION_OVERLAP_RATIO * len(names):
            return entry
    return None


def _item_from_option(option: Option) -> DictionaryItem:
    tech_name = option.tech_name or to_tech_name(option.name)
    return DictionaryItem(code=tech_name.upper(), name=option.name, tech_name=tech_name)


def _prefix_tech_name(phone_tech_name: str) -> str:
    # `numer_telefonu_inna_osoba` → `numer_kierunkowy_inna_osoba` (sufiks kontekstu jak we wzorcu).
    for stem in ("numer_telefonu", "telefon"):
        if phone_tech_name.startswith(stem):
            return "numer_kierunkowy" + phone_tech_name[len(stem) :]
    return f"numer_kierunkowy_{phone_tech_name}" if phone_tech_name else "numer_kierunkowy"


def _walk(fields: Iterable[Field]) -> Iterator[Field]:
    for field in fields:
        yield field
        yield from _walk(q.field for q in field.repeating_section_grid)
