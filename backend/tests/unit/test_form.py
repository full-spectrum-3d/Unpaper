import json
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.form import (
    Field,
    FieldType,
    Flow,
    FormDefinition,
    Question,
    Tab,
    to_document_format,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
MATERIALS = os.environ.get("COI_MATERIALS_DIR")

_BASE_DEFAULTS: dict[str, Any] = {
    "title": "",
    "description": "",
    "options": [],
    "validation": [],
    "readOnly": False,
    "repeatingSectionGrid": [],
    "states": [],
    "questionOrder": 0,
    "tooltipMessage": "",
}


def _with_base_defaults(node: Any) -> Any:
    """Kopia, w której każdy `field` ma komplet kluczy bazowych (spec LLM §5.8)."""
    if isinstance(node, list):
        return [_with_base_defaults(v) for v in node]
    if not isinstance(node, dict):
        return node
    out = {k: _with_base_defaults(v) for k, v in node.items()}
    if "field" in out and isinstance(out["field"], dict):
        out["field"] = {**_BASE_DEFAULTS, **out["field"]}
        if out["field"]["validation"] == {}:  # wzorzec ma czasem `{}` zamiast listy
            out["field"]["validation"] = []
    return out


def _assert_roundtrip(legacy: dict[str, Any]) -> None:
    """Wzorzec po tłumaczeniu na format z dokumentu przechodzi przez model bez zmian."""
    source = to_document_format(legacy)[0]
    out = FormDefinition.model_validate(source).to_import_json()
    assert out == _with_base_defaults(source)


def test_excerpt_roundtrip() -> None:
    _assert_roundtrip(json.loads((FIXTURES / "form" / "excerpt.json").read_text(encoding="utf-8")))


@pytest.mark.skipif(not MATERIALS, reason="brak COI_MATERIALS_DIR")
def test_full_golden_roundtrip() -> None:
    files = sorted(Path(str(MATERIALS)).rglob("konfiguracja_form_*.json"))
    assert files, "brak wzorców w COI_MATERIALS_DIR"
    for path in files:
        _assert_roundtrip(json.loads(path.read_text(encoding="utf-8")))


def _minimal(field: Field) -> dict[str, Any]:
    form = FormDefinition(
        title="t",
        tabs=[
            Tab(
                id="a",
                title="A",
                type="MAIN",
                questions=[Question(x=0, y=0, rows=1, cols=3, field=field)],
            )
        ],
        flow=Flow(links=[]),
    )
    out: dict[str, Any] = form.to_import_json()["tabs"][0]["questions"][0]["field"]
    return out


def test_base_keys_always_present() -> None:
    field = _minimal(Field(id="u", type=FieldType.TEXT_FIELD, tech_name="imie"))
    assert set(field) == {
        "id", "type", "techName", "title", "description", "options", "validation",
        "readOnly", "repeatingSectionGrid", "states", "questionOrder", "tooltipMessage",
    }  # fmt: skip


def test_default_value_is_string_for_select() -> None:
    field = _minimal(
        Field(
            id="u",
            type=FieldType.SELECT,
            tech_name="kraj",
            default_value="Polska",
            dictionary_name="Kraje",
        )
    )
    assert field["defaultValue"] == "Polska"
    assert field["dictionaryName"] == "Kraje"


def test_default_value_list_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Field(id="u", type=FieldType.SELECT, tech_name="kraj", default_value=["Polska"])


def test_unknown_validator_rejected() -> None:
    with pytest.raises(ValidationError):
        Field.model_validate(
            {"id": "u", "type": "TEXT_FIELD", "techName": "x", "validation": ["PHONE"]}
        )


def test_empty_object_validation_becomes_list() -> None:
    field = Field.model_validate(
        {"id": "u", "type": "TEXT_FIELD", "techName": "x", "validation": {}}
    )
    assert field.validation == []


# --- Format z OpisImportowanegoPlikuJSON.md ---


def _legacy_form() -> dict[str, Any]:
    consent = {
        "id": "c",
        "type": "CONSENT_SECTION",
        "techName": "zgoda",
        "consentSectionConfig": {
            "consents": [
                {"description": "a", "required": False},
                {"description": "b", "required": True},
            ],
            "files": [],
        },
        "selectAllEnabled": True,
    }
    country = {
        "id": "k",
        "type": "SELECT",
        "techName": "kraj",
        "defaultValue": ["Polska"],
        "searchEnabled": True,
        "multiLevelTree": False,
        "validation": {},
        "states": [{"type": "SHOW", "query": "x.field.repetingSectionGrid['a' in field.techName]"}],
    }
    section = {
        "id": "s",
        "type": "SECTION",
        "techName": "sekcja",
        "repetingSectionGrid": [
            {"x": 0, "y": 0, "rows": 1, "cols": 3, "minItemRows": 1, "field": country},
            {"x": 0, "y": 1, "rows": 1, "cols": 3, "field": consent},
        ],
    }
    return {"tabs": [{"questions": [{"x": 0, "y": 0, "rows": 1, "cols": 3, "field": section}]}]}


def test_to_document_format_translates_legacy_keys() -> None:
    legacy = _legacy_form()
    before = json.dumps(legacy)
    out, changes = to_document_format(legacy)
    assert json.dumps(legacy) == before  # wejście bez zmian
    assert changes
    section = out["tabs"][0]["questions"][0]["field"]
    assert "repetingSectionGrid" not in section  # literówka z dokumentu -> poprawna nazwa
    first, second = section["repeatingSectionGrid"]
    assert "minItemRows" not in first
    country, consent = first["field"], second["field"]
    assert country["defaultValue"] == "Polska"
    assert country["validation"] == []
    assert not {"searchEnabled", "multiLevelTree"} & set(country)
    assert country["states"][0]["query"] == "x.field.repeatingSectionGrid['a' in field.techName]"
    assert "selectAllEnabled" not in consent
    assert consent["consentSectionConfig"] == {
        "consents": [{"description": "a"}, {"description": "b"}],
        "required": True,
        "files": [],
    }


def test_to_document_format_keeps_document_form() -> None:
    out, _ = to_document_format(_legacy_form())
    again, changes = to_document_format(out)
    assert changes == []
    assert again == out


def test_empty_list_default_value_is_dropped() -> None:
    legacy = _legacy_form()
    country = legacy["tabs"][0]["questions"][0]["field"]["repetingSectionGrid"][0]["field"]
    country["defaultValue"] = []
    out, _ = to_document_format(legacy)
    assert (
        "defaultValue"
        not in out["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]
    )


def test_model_rejects_keys_outside_document() -> None:
    for key in ("searchEnabled", "multiLevelTree", "selectAllEnabled", "repetingSectionGrid"):
        with pytest.raises(ValidationError):
            Field.model_validate({"id": "u", "type": "SELECT", "techName": "k", key: True})
