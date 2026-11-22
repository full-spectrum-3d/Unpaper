"""Poprawki szablonu adresu, walidatorów NIP/REGON i duplikatów pełnomocnictwa."""

import itertools
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from app.models.draft import (
    ApplicantKind,
    Condition,
    DraftField,
    DraftPage,
    DraftSection,
    FormDraft,
)
from app.models.form import Validator
from app.pipeline.build import BuildOptions, BuildResult, build_form
from app.pipeline.build.fields import label_semantic, map_draft_field
from app.pipeline.build.ir import Semantic
from app.pipeline.issues import IssueCode
from app.pipeline.verify import verify_form

ALL_KINDS: list[ApplicantKind] = ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]
SUFFIXES = ["", "_siedziba", "_inna_osoba"]
W41 = IssueCode.W41_POWER_OF_ATTORNEY_DUPLICATE_REMOVED


def counter() -> Callable[[], str]:
    numbers = itertools.count(1)
    return lambda: f"id{next(numbers)}"


def opts() -> BuildOptions:
    return BuildOptions(id_factory=counter(), rodo_clause_url="https://bip.example/rodo")


def fld(id: str, label: str, kind: Any = "short_text", **kwargs: Any) -> DraftField:
    kwargs.setdefault("required", False)
    return DraftField(id=id, label=label, kind=kind, **kwargs)


def page(title: str, *fields: DraftField) -> DraftPage:
    return DraftPage(
        title=title, sections=[DraftSection(title=title, repeating=False, fields=list(fields))]
    )


def make_draft(*pages: DraftPage, **kwargs: Any) -> FormDraft:
    data: dict[str, Any] = {
        "title": "Wniosek o X",
        "authority_kind": "URZAD",
        "authority_name": "Urząd Gminy",
        "applicant_kinds": ["SELF"],
        "subject_pages": list(pages),
    }
    data.update(kwargs)
    return FormDraft.model_validate(data)


def walk_fields(form: dict[str, Any]) -> Iterator[dict[str, Any]]:
    def rec(field: dict[str, Any]) -> Iterator[dict[str, Any]]:
        yield field
        for child in field["repeatingSectionGrid"]:
            yield from rec(child["field"])

    for tab in form["tabs"]:
        for question in tab["questions"]:
            yield from rec(question["field"])


def fields_by_tech(form: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["techName"]: f for f in walk_fields(form)}


def build(draft: FormDraft) -> tuple[BuildResult, dict[str, Any]]:
    result = build_form(draft, opts())
    form = result.form.to_import_json()
    verified = verify_form(form, autofix=False)
    assert verified.valid, verified.errors
    return result, form


def show_queries(field: dict[str, Any]) -> list[str]:
    return [s["query"] for s in field["states"] if s["type"] == "SHOW"]


# --- #1: numer lokalu wymagany ---


def test_apartment_number_is_required_for_every_address() -> None:
    _, form = build(make_draft(applicant_kinds=ALL_KINDS))
    fields = fields_by_tech(form)
    for suffix in SUFFIXES:
        apartment = fields[f"numer_lokalu{suffix}"]
        assert apartment["validation"] == ["REQUIRED"]
        (query,) = show_queries(apartment)
        assert "$not(" in query
        assert "Brak numeru lokalu" in query
        assert f"brak_numeru_lokalu{suffix}" in query


# --- #2: polski adres bez checkboxa „Brak kodu pocztowego” ---


def test_polish_zip_code_has_no_opt_out_checkbox() -> None:
    _, form = build(make_draft(applicant_kinds=ALL_KINDS))
    fields = fields_by_tech(form)
    for suffix in SUFFIXES:
        assert f"brak_kodu_pocztowego{suffix}" not in fields
        zip_code = fields[f"kod_pocztowy{suffix}"]
        assert zip_code["validation"] == ["REQUIRED", "ZIP_CODE"]
        (query,) = show_queries(zip_code)
        assert "Polska" in query
        assert f"kraj{suffix}" in query
        assert "Brak kodu pocztowego" not in query
        assert "$not(" not in query


def test_foreign_zip_code_keeps_opt_out_checkbox() -> None:
    _, form = build(make_draft(applicant_kinds=ALL_KINDS))
    fields = fields_by_tech(form)
    for suffix in SUFFIXES:
        box = fields[f"brak_kodu_pocztowego{suffix}_zagranica"]
        assert box["type"] == "CHECKBOX"
        assert box["options"][0]["name"] == "Brak kodu pocztowego"
        (query,) = show_queries(fields[f"kod_pocztowy{suffix}_zagranica"])
        assert "Brak kodu pocztowego" in query


# --- #8: wspólne pole NIP/REGON ---


@pytest.mark.parametrize(
    "label",
    [
        "NIP/REGON",
        "NIP lub REGON",
        "NIP/REGON (dot. tylko osób prawnych)",
        "REGON / NIP",
        "PESEL lub NIP",
    ],
)
def test_shared_identifier_label_gets_no_format_validator(label: str) -> None:
    assert label_semantic(label) is None
    node, _ = map_draft_field(fld("f1", label, required=True), key="k")
    assert node.validation == [Validator.REQUIRED]
    optional, _ = map_draft_field(fld("f1", label), key="k")
    assert optional.validation == []


@pytest.mark.parametrize(
    ("label", "semantic", "validator"),
    [
        ("NIP", Semantic.NIP, Validator.NIP),
        ("Numer NIP", Semantic.NIP, Validator.NIP),
        ("REGON", Semantic.REGON, Validator.REGON),
        ("Numer PESEL", Semantic.PESEL, Validator.PESEL),
    ],
)
def test_single_identifier_label_keeps_validator(
    label: str, semantic: Semantic, validator: Validator
) -> None:
    assert label_semantic(label) is semantic
    node, _ = map_draft_field(fld("f1", label, required=True), key="k")
    assert node.validation == [Validator.REQUIRED, validator]


# --- #4: duplikaty pełnomocnictwa ---

_POWER_OF_ATTORNEY = "Dokument stwierdzający udzielenie pełnomocnictwa"
_STAMP_DUTY = "Dowód uiszczenia opłaty skarbowej za pełnomocnictwo"
_YES_NO = ["Tak", "Nie"]


def _subject_page() -> DraftPage:
    return page(
        "Przedmiot",
        fld("f1", "Opis sprawy", "long_text", required=True),
        fld("f2", "Pełnomocnictwo", "file", required=True),
        fld("f3", _POWER_OF_ATTORNEY, "single_choice", required=True, options=_YES_NO),
        fld(
            "f4",
            "Data udzielenia pełnomocnictwa",
            "date",
            visible_when=[Condition(field_id="f3", op="equals", value="Tak")],
        ),
        fld("f5", "Numer pełnomocnictwa"),
        fld("f6", "Dowód uiszczenia opłaty skarbowej", "file"),
        fld("f7", _STAMP_DUTY, "single_choice", options=["tak", "NIE"]),
    )


def _attorney_draft(kinds: list[ApplicantKind]) -> FormDraft:
    return make_draft(
        _subject_page(),
        applicant_kinds=kinds,
        attachments=[_POWER_OF_ATTORNEY, _STAMP_DUTY, "Kopia decyzji"],
    )


def _titles(form: dict[str, Any]) -> list[str]:
    """Etykiety pól (bez sekcji: predefiniowana nazywa się „Pełnomocnictwo”)."""
    return [f["title"] for f in walk_fields(form) if f["type"] != "SECTION"]


def test_power_of_attorney_duplicates_removed_when_section_is_predefined() -> None:
    result, form = build(_attorney_draft(["SELF", "OTHER_PERSON"]))
    fields = fields_by_tech(form)
    titles = _titles(form)

    # Pełnomocnictwo zbiera tylko sekcja predefiniowana, widoczna warunkowo.
    uploads = [f for f in walk_fields(form) if "pełnomocnictw" in f["title"].casefold()]
    assert [f["techName"] for f in uploads if f["type"] == "FILE_UPLOADER"] == [
        "plik_dokumentu_z_pelnomocnictwem"
    ]
    assert show_queries(fields["pelnomocnictwo"])
    for label in ("Pełnomocnictwo", _POWER_OF_ATTORNEY, _STAMP_DUTY):
        assert label not in titles

    # Pola innego typu i bez „pełnomocnictwa” zostają.
    assert "Numer pełnomocnictwa" in titles
    assert "Dowód uiszczenia opłaty skarbowej" in titles
    assert "Kopia decyzji" in titles
    # Warunek wskazujący usunięte pole znika: pole jest zawsze widoczne.
    assert show_queries(fields["data_udzielenia_pelnomocnictwa"]) == []

    removed = [w for w in result.warnings if w.code == W41]
    assert len(removed) == 5
    assert all("sekcja predefiniowana" in w.message for w in removed)
    assert {w.path for w in removed} == {
        "attachments[0]",
        "attachments[1]",
        "subject_pages[0].sections[0].fields[1]",
        "subject_pages[0].sections[0].fields[2]",
        "subject_pages[0].sections[0].fields[6]",
    }
    assert IssueCode.W03_CONDITION_UNRESOLVED not in [w.code for w in result.warnings]


@pytest.mark.parametrize("kinds", [["LEGAL_ENTITY"], ["OTHER_PERSON"], ALL_KINDS])
def test_power_of_attorney_duplicates_removed_for_any_representation(
    kinds: list[ApplicantKind],
) -> None:
    result, form = build(_attorney_draft(kinds))
    assert "Pełnomocnictwo" not in _titles(form)
    assert any(w.code == W41 for w in result.warnings)


def test_power_of_attorney_fields_kept_without_predefined_section() -> None:
    result, form = build(_attorney_draft(["SELF"]))
    titles = _titles(form)
    assert fields_by_tech(form)["pelnomocnictwo"]["type"] == "FILE_UPLOADER"
    assert "Pełnomocnictwo" in titles
    assert _POWER_OF_ATTORNEY in titles
    assert _STAMP_DUTY in titles
    assert W41 not in [w.code for w in result.warnings]


def test_empty_section_and_page_removed_after_dropping_duplicates() -> None:
    draft = make_draft(
        page("Przedmiot", fld("f1", "Opis sprawy", "long_text")),
        page("Załączniki do wniosku", fld("f2", "Pełnomocnictwo", "file", required=True)),
        applicant_kinds=["SELF", "OTHER_PERSON"],
    )
    _, form = build(draft)
    assert [t["title"] for t in form["tabs"]] == [
        "Dane",
        "Przedmiot",
        "Kontakt i zgody",
        "Strona końcowa",
    ]


def test_attachment_dedup_is_approximate() -> None:
    draft = make_draft(
        page("Przedmiot", fld("f1", "Kopia decyzji o pozwoleniu na budowę", "file")),
        attachments=["Kopia decyzji", "Mapa sytuacyjna"],
    )
    result, form = build(draft)
    titles = _titles(form)
    assert "Kopia decyzji" not in titles
    assert "Mapa sytuacyjna" in titles
    duplicates = [w for w in result.warnings if w.code == IssueCode.W10_ATTACHMENT_DUPLICATE]
    assert len(duplicates) == 1
    assert "Kopia decyzji" in duplicates[0].message


def test_attachment_dedup_matches_longer_attachment_name() -> None:
    draft = make_draft(
        page("Przedmiot", fld("f1", "Kopia decyzji", "file")),
        attachments=["Kopia decyzji o pozwoleniu na budowę"],
    )
    result, form = build(draft)
    assert "Kopia decyzji o pozwoleniu na budowę" not in _titles(form)
    assert IssueCode.W10_ATTACHMENT_DUPLICATE in [w.code for w in result.warnings]
