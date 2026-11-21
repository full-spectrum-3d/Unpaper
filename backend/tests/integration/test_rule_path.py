"""Ścieżka bez LLM: bloki ekstrakcji → szkic z reguł → poprawki → build → verify.

Wejściem są zapisane bloki ekstrakcji prawdziwych wniosków (`tests/fixtures/documents/`),
więc test nie wymaga modelu, LibreOffice ani OCR i działa w domyślnym przebiegu pytest.
Oczekiwania pochodzą z wizualizacji formularzy w `wymagania/`.
"""

from pathlib import Path
from typing import Any

import pytest

from app.models.document import DocumentModel
from app.models.draft import FormDraft
from app.pipeline.build import BuildOptions, build_form
from app.pipeline.draft_normalize import normalize_draft
from app.pipeline.rule_draft import rule_draft
from app.pipeline.verify import verify_form

DOCUMENTS = Path(__file__).parents[1] / "fixtures" / "documents"

# Tytuły stron (po stronie „Dane”) i pola przedmiotu sprawy, które musi dać sama ścieżka reguł.
EXPECTED: dict[str, dict[str, Any]] = {
    "nadplata": {
        "tabs": [
            "Dane",
            "Stwierdzenie nadpłaty podatku",
            "Kontakt i zgody",
            "Strona końcowa",
        ],
        "fields": {
            "Rodzaj podatku",
            "Kwota",
            "Uzasadnienie",
            "Numer rachunku",
            "Korekta deklaracji",
        },
        "states": 31,  # tyle samo, co we wzorcu COI
    },
    "numer_porzadkowy": {
        "tabs": ["Dane", "Ustalenie numeru porządkowego", "Kontakt i zgody", "Strona końcowa"],
        "fields": {"Miejscowość", "Ulica", "Numer ewidencyjny działki", "Obręb"},
        "states": 29,
    },
}


def _draft(name: str) -> tuple[FormDraft, DocumentModel]:
    doc = DocumentModel.model_validate_json(
        (DOCUMENTS / f"{name}.json").read_text(encoding="utf-8")
    )
    draft = rule_draft(doc)
    assert draft is not None
    draft, _ = normalize_draft(draft, doc)
    return draft, doc


def _build(draft: FormDraft) -> dict[str, Any]:
    options = BuildOptions(identity_source="PESEL")
    return build_form(draft, options).form.to_import_json()


def _walk(form: dict[str, Any]) -> list[dict[str, Any]]:
    """Wszystkie pola formularza (sekcje i ich pola) jako płaska lista."""
    found: list[dict[str, Any]] = []

    def visit(field: dict[str, Any]) -> None:
        found.append(field)
        for question in field.get("repeatingSectionGrid", []):
            visit(question["field"])

    for tab in form["tabs"]:
        for question in tab["questions"]:
            visit(question["field"])
    return found


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_rule_path_builds_valid_form(name: str) -> None:
    draft, _ = _draft(name)
    form = _build(draft)

    result = verify_form(form, autofix=False)
    assert result.valid, result.errors

    expected = EXPECTED[name]
    assert [tab["title"] for tab in form["tabs"]] == expected["tabs"]
    titles = {field["title"] for field in _walk(form)}
    assert expected["fields"] <= titles
    states = sum(len(field.get("states", [])) for field in _walk(form))
    assert states >= expected["states"]


def test_nadplata_settlement_choice_controls_dependent_fields() -> None:
    draft, _ = _draft("nadplata")
    fields = {f.label: f for _, f in draft.iter_fields()}
    choice = fields["Kwotę nadpłaty"]
    assert choice.kind == "single_choice" and len(choice.options) == 2
    for label, option in (("Tytuł", choice.options[0]), ("Numer rachunku", choice.options[1])):
        assert [(c.field_id, c.value) for c in fields[label].visible_when] == [(choice.id, option)]

    by_title = {f["title"]: f for f in _walk(_build(draft)) if f["type"] != "SECTION"}
    for label in ("Tytuł", "Numer rachunku"):
        assert [s["type"] for s in by_title[label]["states"]] == ["SHOW"]
    assert by_title["Kwotę nadpłaty"]["type"] == "RADIO"


def test_nadplata_file_stays_in_subject_page_not_attachments() -> None:
    draft, _ = _draft("nadplata")
    assert draft.attachments == []
    form = _build(draft)
    subject = next(t for t in form["tabs"] if t["title"] == "Stwierdzenie nadpłaty podatku")
    contact = next(t for t in form["tabs"] if t["title"] == "Kontakt i zgody")
    in_subject = {q["field"]["title"] for q in subject["questions"]}
    assert "Korekta deklaracji" in in_subject
    assert "Załączniki" not in {q["field"]["title"] for q in contact["questions"]}


def test_numer_porzadkowy_labels_are_nouns_without_abbreviations() -> None:
    draft, _ = _draft("numer_porzadkowy")
    labels = [f.label for _, f in draft.iter_fields()]
    assert labels == ["Miejscowość", "Ulica", "Numer ewidencyjny działki", "Obręb"]
