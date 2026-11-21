"""Propozycje nowych słowników dla gotowego formularza (spec §8.6).

Pole wyboru albo tekstowe, którego lista ma charakter zamknięty i ogólnokrajowy
(rodzaj podatku, rodzaj dokumentu tożsamości...), a w katalogu brakuje słownika,
zachowuje opcje inline. Propozycja słownika trafia do raportu konwersji.

Działa na `FormDefinition`, więc nie zależy od wewnętrznej reprezentacji `build/`.
"""

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

from app.models.dictionary import DictionaryItem, DictionaryProposal
from app.models.form import Field, FieldType, FormDefinition, Option
from app.pipeline.build.fields import slugify

_CANDIDATE_TYPES = frozenset(
    {FieldType.TEXT_FIELD, FieldType.SELECT, FieldType.RADIO, FieldType.CHECKBOX}
)
# Lista z blankietu to ta sama lista, gdy ≥ 2 i ≥ połowa jej opcji to pozycje propozycji.
_MIN_OPTION_OVERLAP = 2
_OPTION_OVERLAP_RATIO = 0.5
_LABEL_NOISE = re.compile(r"\(\s*(opcjonalnie|wymagane|nieobowiązkowe)\s*\)|[*:]")


@dataclass(frozen=True)
class ProposalTemplate:
    name: str
    title: str
    description: str
    field_types: tuple[FieldType, ...]
    item_structure: tuple[str, ...]
    label_patterns: tuple[re.Pattern[str], ...]
    items: tuple[DictionaryItem, ...]

    def to_catalog_json(self) -> dict[str, Any]:
        """Wpis `GET /dictionaries` (format jak propozycja w raporcie)."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "status": "PROPOSED",
            "fieldTypes": list(self.field_types),
            "itemStructure": list(self.item_structure),
            "items": [i.model_dump(by_alias=True, exclude_none=True) for i in self.items],
        }


@cache
def load_proposal_catalog() -> tuple[ProposalTemplate, ...]:
    raw = files("app.resources").joinpath("dictionary_proposals.json").read_text(encoding="utf-8")
    return tuple(
        ProposalTemplate(
            name=item["name"],
            title=item["title"],
            description=item["description"],
            field_types=tuple(FieldType(t) for t in item["fieldTypes"]),
            item_structure=tuple(item["itemStructure"]),
            label_patterns=tuple(re.compile(p) for p in item["labelPatterns"]),
            items=tuple(
                DictionaryItem(
                    code=i["code"],
                    name=i["name"],
                    tech_name=i.get("techName") or slugify(i["name"]),
                    valid_from=i.get("validFrom"),
                    valid_to=i.get("validTo"),
                )
                for i in item["items"]
            ),
        )
        for item in json.loads(raw)
    )


def normalize_label(label: str) -> str:
    """Etykieta do porównań: małe litery, bez `*`, `:` i dopisków `(opcjonalnie)`."""
    return " ".join(_LABEL_NOISE.sub(" ", label.casefold()).split())


def propose_dictionaries(form: FormDefinition) -> list[DictionaryProposal]:
    """Propozycje słowników dla pól formularza, w kolejności katalogu."""
    return propose_for_fields(q.field for tab in form.tabs for q in tab.questions)


def propose_for_fields(fields: Iterable[Field]) -> list[DictionaryProposal]:
    """Jak `propose_dictionaries`, dla dowolnych pól (z polami sekcji włącznie)."""
    templates = load_proposal_catalog()
    used_by: dict[str, list[str]] = {}
    extra: dict[str, list[DictionaryItem]] = {}

    for field in _walk(fields):
        if field.dictionary_name or field.type not in _CANDIDATE_TYPES:
            continue
        template = _match_label(field.title, templates) or _match_options(field.options, templates)
        if template is None:
            continue
        names = used_by.setdefault(template.name, [])
        if field.tech_name not in names:
            names.append(field.tech_name)
        extras = extra.setdefault(template.name, [])
        known = {normalize_label(i.name) for i in (*template.items, *extras)}
        for option in field.options:
            key = normalize_label(option.name)
            if key not in known:
                known.add(key)
                tech_name = option.tech_name or slugify(option.name)
                extras.append(
                    DictionaryItem(code=tech_name.upper(), name=option.name, tech_name=tech_name)
                )

    return [
        DictionaryProposal(
            name=t.name,
            title=t.title,
            description=t.description,
            item_structure=t.item_structure,
            items=(*t.items, *extra[t.name]),
            used_by=tuple(used_by[t.name]),
        )
        for t in templates
        if t.name in used_by
    ]


def _match_label(label: str, templates: Iterable[ProposalTemplate]) -> ProposalTemplate | None:
    text = normalize_label(label)
    if not text:
        return None
    return next((t for t in templates if any(p.match(text) for p in t.label_patterns)), None)


def _match_options(
    options: list[Option], templates: Iterable[ProposalTemplate]
) -> ProposalTemplate | None:
    if len(options) < _MIN_OPTION_OVERLAP:
        return None
    names = {normalize_label(o.name) for o in options}
    for template in templates:
        overlap = len(names & {normalize_label(i.name) for i in template.items})
        if overlap >= _MIN_OPTION_OVERLAP and overlap >= _OPTION_OVERLAP_RATIO * len(names):
            return template
    return None


def _walk(fields: Iterable[Field]) -> Iterator[Field]:
    for field in fields:
        yield field
        yield from _walk(q.field for q in field.repeating_section_grid)
