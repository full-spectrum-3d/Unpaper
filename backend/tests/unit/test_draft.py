import copy
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.draft import FormDraft, llm_schema
from app.models.warning import ConversionWarning

Draft = dict[str, Any]


def _field(fid: str, label: str, kind: str = "short_text", **kw: Any) -> Draft:
    return {"id": fid, "label": label, "kind": kind, "required": True, **kw}


def _draft() -> Draft:
    return {
        "title": "Wniosek o ustalenie numeru porządkowego nieruchomości",
        "authority_kind": "ORGAN",
        "authority_name": "Wójt Gminy Elbląg",
        "applicant_kinds": ["SELF", "OTHER_PERSON"],
        "attachments": [],
        "statements": [],
        "subject_pages": [
            {
                "title": "Informacje o budynku",
                "sections": [
                    {
                        "title": "Lokalizacja budynku",
                        "repeating": False,
                        "fields": [
                            _field("f1", "Miejscowość"),
                            _field("f2", "Ulica"),
                            _field("f3", "Numer ewidencyjny działki"),
                            _field("f4", "Obręb"),
                            _field(
                                "f5",
                                "Czy budynek jest w budowie?",
                                "single_choice",
                                options=["Tak", "Nie"],
                            ),
                            _field(
                                "f6",
                                "Data rozpoczęcia budowy",
                                visible_when=[{"field_id": "f5", "op": "equals", "value": "Tak"}],
                            ),
                        ],
                    }
                ],
            }
        ],
    }


def _fields(d: Draft) -> list[Draft]:
    fields: list[Draft] = d["subject_pages"][0]["sections"][0]["fields"]
    return fields


def dup_id(d: Draft) -> Draft:
    _fields(d)[1]["id"] = "f1"
    return d


def cond_to(target: str) -> Callable[[Draft], Draft]:
    def mutate(d: Draft) -> Draft:
        _fields(d)[5]["visible_when"][0]["field_id"] = target
        return d

    return mutate


def cond_value(value: str) -> Callable[[Draft], Draft]:
    def mutate(d: Draft) -> Draft:
        _fields(d)[5]["visible_when"][0]["value"] = value
        return d

    return mutate


def applicant_kinds(kinds: list[str]) -> Callable[[Draft], Draft]:
    def mutate(d: Draft) -> Draft:
        d["applicant_kinds"] = kinds
        return d

    return mutate


def title(value: str) -> Callable[[Draft], Draft]:
    def mutate(d: Draft) -> Draft:
        d["title"] = value
        return d

    return mutate


def empty_section(d: Draft) -> Draft:
    d["subject_pages"][0]["sections"][0]["fields"] = []
    return d


def test_valid_draft_parses() -> None:
    draft = FormDraft.model_validate(_draft())
    paths = [p for p, _ in draft.iter_fields()]
    assert paths[0] == "subject_pages[0].sections[0].fields[0]"
    assert len(paths) == 6


def test_optional_lists_default_empty() -> None:
    d = _draft()
    del d["attachments"]
    del d["statements"]
    assert "options" not in _fields(d)[0]
    draft = FormDraft.model_validate(d)
    assert draft.attachments == [] and draft.statements == []
    assert next(f for _, f in draft.iter_fields()).options == []


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (dup_id, "f1"),
        (cond_to("f9"), "f9"),
        (cond_to("f1"), "f1"),
        (cond_to("f6"), "f6"),
        (cond_value("Może"), "Może"),
        (applicant_kinds([]), "applicant_kinds"),
        (applicant_kinds(["SELF", "SELF"]), "applicant_kinds"),
        (title("  "), "title"),
        (empty_section, "fields"),
    ],
)
def test_invalid_draft_rejected(mutate: Callable[[Draft], Draft], fragment: str) -> None:
    with pytest.raises(ValidationError) as exc:
        FormDraft.model_validate(mutate(copy.deepcopy(_draft())))
    assert fragment in str(exc.value)


def test_extra_keys_rejected() -> None:
    d = _draft()
    _fields(d)[0]["semantic"] = "PESEL"
    with pytest.raises(ValidationError):
        FormDraft.model_validate(d)


def test_llm_schema_is_flat_and_non_nullable() -> None:
    schema = llm_schema()
    assert '"null"' not in json.dumps(schema)
    for name, sub in schema["$defs"].items():
        assert f"#/$defs/{name}" not in json.dumps(sub)


def test_warning_code_format() -> None:
    ConversionWarning(code="W01_LLM_FALLBACK", message="x")
    with pytest.raises(ValidationError):
        ConversionWarning(code="llm", message="x")
