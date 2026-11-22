"""Normalizacja struktury szkicu: pliki z „W załączeniu”, powtarzane grupy pól, bloki zgód
i rodzaje wnioskodawcy."""

import copy
from typing import Any

from app.models.document import DocumentModel
from app.models.draft import FormDraft
from app.pipeline.draft_normalize import normalize_draft
from llm_eval.run import load_cases
from tests.unit.test_draft import _draft
from tests.unit.test_draft_normalize import DOC, _codes, _doc_blocks

LOCATION = ("paragraph", "Miejscowość Ulica Numer ewidencyjny działki Obręb.")


def _f(fid: str, label: str, kind: str = "short_text", **kw: Any) -> dict[str, Any]:
    return {"id": fid, "label": label, "kind": kind, "required": kind != "info", **kw}


def _with_section(
    *fields: dict[str, Any], title: str = "Powierzchnia zajęcia", **changes: Any
) -> FormDraft:
    """Szkic z przykładowej sekcji (f1-f4) i - gdy podano pola - drugiej sekcji z nimi."""
    d = copy.deepcopy(_draft())
    section = d["subject_pages"][0]["sections"][0]
    section["fields"] = section["fields"][:4]
    if fields:
        d["subject_pages"][0]["sections"].append(
            {"title": title, "repeating": False, "fields": list(fields)}
        )
    d.update(changes)
    return FormDraft.model_validate(d)


def _labels(draft: FormDraft, section: int = -1) -> list[str]:
    return [f.label for f in draft.subject_pages[0].sections[section].fields]


# --- #7: pliki z „W załączeniu:” ---

INLINE_DOC = _doc_blocks(
    LOCATION,
    ("label", "w załączeniu:"),
    ("paragraph", "1) korekta deklaracji"),
    ("paragraph", "2) ......................"),
)


def test_inline_attachment_turns_text_field_into_file() -> None:
    cond = [{"field_id": "f5", "op": "equals", "value": "Tak"}]
    draft = _with_section(
        _f("f5", "Czy korekta?", "single_choice", options=["Tak", "Nie"]),
        _f("f6", "Korekta deklaracji", visible_when=cond),
        title="Korekta",
    )
    out, warnings = normalize_draft(draft, INLINE_DOC)
    field = out.subject_pages[0].sections[-1].fields[1]
    assert (field.id, field.label, field.kind, field.options) == (
        "f6",
        "Korekta deklaracji",
        "file",
        [],
    )
    assert field.required and [c.field_id for c in field.visible_when] == ["f5"]
    assert "W44_FILE_FIELD_FROM_DOCUMENT" in _codes(warnings)
    assert out.attachments == [] and "W34_ATTACHMENT_FROM_DOCUMENT" not in _codes(warnings)


def test_inline_attachment_with_file_field_unchanged() -> None:
    draft = _with_section(_f("f5", "Plik korekty deklaracji", "file"), title="Korekta")
    out, warnings = normalize_draft(draft, INLINE_DOC)
    assert _labels(out) == ["Plik korekty deklaracji"] and out.attachments == []
    assert not {"W44_FILE_FIELD_FROM_DOCUMENT", "W34_ATTACHMENT_FROM_DOCUMENT"} & set(
        _codes(warnings)
    )


def test_inline_attachment_without_field_goes_to_attachments() -> None:
    draft = _with_section(_f("f5", "Rodzaj podatku"), title="Podatek")
    out, warnings = normalize_draft(draft, INLINE_DOC)
    assert out.attachments == ["Korekta deklaracji"]
    assert "W34_ATTACHMENT_FROM_DOCUMENT" in _codes(warnings)
    assert out.subject_pages[0].sections[-1].fields[0].kind == "short_text"


def test_inline_attachment_already_listed_not_repeated() -> None:
    out, warnings = normalize_draft(_with_section(attachments=["Korekta deklaracji"]), INLINE_DOC)
    assert out.attachments == ["Korekta deklaracji"]
    assert "W34_ATTACHMENT_FROM_DOCUMENT" not in _codes(warnings)


def test_overpayment_case_correction_becomes_file() -> None:
    doc = load_cases(["nadplata"])[0]["doc"]
    draft = _with_section(_f("f5", "Korekta deklaracji"), title="Załączniki do wniosku")
    out, warnings = normalize_draft(draft, doc)
    kinds = {f.label: f.kind for _, f in out.iter_fields()}
    assert kinds["Korekta deklaracji"] == "file"
    assert "W44_FILE_FIELD_FROM_DOCUMENT" in _codes(warnings)


# --- #9: powtarzane grupy pól ---

AREA_DOC = _doc_blocks(
    LOCATION,
    ("paragraph", "jezdnia długość szerokość chodnik długość szerokość"),
)


def test_repeated_group_kept_and_numbered() -> None:
    draft = _with_section(
        _f("f5", "Długość", "number"),
        _f("f6", "Szerokość", "number"),
        _f("f7", "Długość", "number"),
        _f("f8", "Szerokość", "number"),
    )
    out, warnings = normalize_draft(draft, AREA_DOC)
    assert _labels(out) == ["Długość (1)", "Szerokość (1)", "Długość (2)", "Szerokość (2)"]
    assert [f.id for f in out.subject_pages[0].sections[-1].fields] == ["f5", "f6", "f7", "f8"]
    assert _codes(warnings).count("W43_REPEATED_FIELDS_NUMBERED") == 1
    assert "W25_DUPLICATE_FIELD_REMOVED" not in _codes(warnings)


def test_repeated_group_labelled_by_preceding_info() -> None:
    draft = _with_section(
        _f("f5", "Jezdnia", "info"),
        _f("f6", "Długość", "number"),
        _f("f7", "Szerokość", "number"),
        _f("f8", "Chodnik", "info"),
        _f("f9", "Długość", "number"),
        _f("f10", "Szerokość", "number"),
    )
    out, warnings = normalize_draft(draft, AREA_DOC)
    assert _labels(out) == [
        "Jezdnia",
        "Długość - Jezdnia",
        "Szerokość - Jezdnia",
        "Chodnik",
        "Długość - Chodnik",
        "Szerokość - Chodnik",
    ]
    assert "W43_REPEATED_FIELDS_NUMBERED" in _codes(warnings)


def test_three_field_group_repeated_three_times() -> None:
    labels = ["Długość", "Szerokość", "Powierzchnia"] * 3
    draft = _with_section(*(_f(f"f{n}", label, "number") for n, label in enumerate(labels, 5)))
    out, _ = normalize_draft(draft, AREA_DOC)
    assert _labels(out)[6:] == ["Długość (3)", "Szerokość (3)", "Powierzchnia (3)"]


def test_single_repeated_label_still_removed() -> None:
    draft = _with_section(
        _f("f5", "Imię"), _f("f6", "Nazwisko"), _f("f7", "Imię"), title="Dane dziecka"
    )
    out, warnings = normalize_draft(draft, AREA_DOC)
    assert _labels(out) == ["Imię", "Nazwisko"]
    assert _codes(warnings).count("W25_DUPLICATE_FIELD_REMOVED") == 1
    assert "W43_REPEATED_FIELDS_NUMBERED" not in _codes(warnings)


def test_road_case_surface_table_kept() -> None:
    doc = load_cases(["pas-drogowy"])[0]["doc"]
    categories = [
        "Jezdnia (do 20% szerokości)",
        "Jezdnia (do 50% szerokości)",
        "Jezdnia (powyżej 50% szerokości)",
        "Chodnik",
    ]
    fields = []
    for category in categories:
        fields += [(category, "number"), ("Długość", "number"), ("Szerokość", "number")]
    draft = _with_section(
        *(_f(f"f{n}", label, kind) for n, (label, kind) in enumerate(fields, 5)),
        title="Powierzchnia zajęcia",
    )
    out, warnings = normalize_draft(draft, doc)
    labels = _labels(out)
    assert len(labels) == 12
    assert labels[1:3] == [
        "Długość - Jezdnia (do 20% szerokości)",
        "Szerokość - Jezdnia (do 20% szerokości)",
    ]
    assert labels[-2:] == ["Długość - Chodnik", "Szerokość - Chodnik"]
    assert "W25_DUPLICATE_FIELD_REMOVED" not in _codes(warnings)
    # Etykieta z kontekstem nie występuje w blankiecie w całości, ale każda jej część tak.
    not_found = [w.message for w in warnings if w.code == "W13_FIELD_NOT_IN_DOCUMENT"]
    assert not [m for m in not_found if "Długość" in m or "Szerokość" in m]


# --- #12: bloki zgody na przetwarzanie danych ---


def test_data_consent_heading_removed_from_data_section() -> None:
    draft = _with_section(
        _f("f5", "Imię i nazwisko kandydata"),
        _f("f6", "Zgoda na przetwarzanie danych osobowych", "info"),
        _f("f7", "Klub sportowy"),
        title="Dane kandydata nieletniego",
    )
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Imię i nazwisko kandydata", "Klub sportowy"]
    assert "W40_DATA_CONSENT_FIELD_REMOVED" in _codes(warnings)
    assert out.statements == []


def test_consent_for_child_moves_to_statements() -> None:
    consent = "Wyrażam zgodę na przetwarzanie danych osobowych mojego dziecka zawartych we wniosku"
    draft = _with_section(
        _f("f5", "Imię i nazwisko kandydata"),
        _f("f6", consent, "info"),
        title="Dane kandydata nieletniego",
    )
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Imię i nazwisko kandydata"]
    assert out.statements == [consent]
    assert "W40_DATA_CONSENT_FIELD_REMOVED" in _codes(warnings)


def test_section_with_only_consent_block_removed() -> None:
    draft = _with_section(
        _f("f5", "Zgoda na przetwarzanie danych osobowych", "info"), title="Informacje"
    )
    out, warnings = normalize_draft(draft, DOC)
    assert [s.title for s in out.subject_pages[0].sections] == ["Lokalizacja budynku"]
    assert "W18_EMPTY_CONTAINER_REMOVED" in _codes(warnings)


def test_other_info_block_and_consent_checkbox_kept() -> None:
    draft = _with_section(
        _f("f5", "Pouczenie o odpowiedzialności karnej", "info"),
        _f("f6", "Zgoda na przetwarzanie danych osobowych", "multi_choice", options=["Tak"]),
        title="Pouczenie",
    )
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == [
        "Pouczenie o odpowiedzialności karnej",
        "Zgoda na przetwarzanie danych osobowych",
    ]
    assert "W40_DATA_CONSENT_FIELD_REMOVED" not in _codes(warnings)


# --- #10: opcja osoby prawnej ---

PERSON_DOC = _doc_blocks(LOCATION, ("paragraph", "Imię i nazwisko wnioskodawcy, PESEL, adres."))
ALL_KINDS = ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]


def test_legal_entity_removed_without_company_data() -> None:
    out, warnings = normalize_draft(_with_section(applicant_kinds=ALL_KINDS), PERSON_DOC)
    assert out.applicant_kinds == ["SELF", "OTHER_PERSON"]
    assert "W42_LEGAL_ENTITY_REMOVED" in _codes(warnings)


def test_legal_entity_only_falls_back_to_persons() -> None:
    draft = _with_section(applicant_kinds=["LEGAL_ENTITY"])
    out, _ = normalize_draft(draft, PERSON_DOC)
    assert out.applicant_kinds == ["SELF", "OTHER_PERSON"]
    draft = _with_section(applicant_kinds=["OTHER_PERSON", "LEGAL_ENTITY"])
    out, _ = normalize_draft(draft, PERSON_DOC)
    assert out.applicant_kinds == ["SELF", "OTHER_PERSON"]


def test_legal_entity_kept_with_company_data() -> None:
    doc = _doc_blocks(LOCATION, ("paragraph", "Imię i nazwisko / nazwa, NIP"))
    out, warnings = normalize_draft(_with_section(applicant_kinds=ALL_KINDS), doc)
    assert out.applicant_kinds == ALL_KINDS
    assert "W42_LEGAL_ENTITY_REMOVED" not in _codes(warnings)


def test_company_seat_in_gdpr_clause_ignored() -> None:
    doc = _doc_blocks(
        LOCATION,
        ("paragraph", "Imię i nazwisko wnioskodawcy"),
        ("heading", "Klauzula informacyjna"),
        ("paragraph", "Administratorem danych jest Wójt Gminy Elbląg z siedzibą w Elblągu."),
    )
    assert "siedzib" not in doc.to_prompt_text(exclude_boilerplate=True)
    out, warnings = normalize_draft(_with_section(applicant_kinds=ALL_KINDS), doc)
    assert out.applicant_kinds == ["SELF", "OTHER_PERSON"]
    assert "W42_LEGAL_ENTITY_REMOVED" in _codes(warnings)


def _case_kinds(slug: str) -> list[str]:
    doc: DocumentModel = load_cases([slug])[0]["doc"]
    out, _ = normalize_draft(_with_section(applicant_kinds=ALL_KINDS), doc)
    return list(out.applicant_kinds)


def test_cases_without_company_data_lose_legal_entity() -> None:
    for slug in ["zaswiadczenie", "swietlica", "psy"]:
        assert _case_kinds(slug) == ["SELF", "OTHER_PERSON"], slug
    for slug in ["numer-porzadkowy", "nadplata", "odpady"]:
        assert _case_kinds(slug) == ALL_KINDS, slug
