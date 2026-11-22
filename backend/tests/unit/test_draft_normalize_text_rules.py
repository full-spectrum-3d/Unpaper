"""Reguły tekstowe normalizacji: data podpisu, pola opcjonalne, pola bez etykiety, oświadczenia."""

from typing import Any

import pytest

from app.models.document import DocumentModel
from app.models.draft import FormDraft
from app.pipeline.draft_normalize import normalize_draft
from app.pipeline.draft_rules import (
    applicant_field_reason,
    is_statement,
    statements_from_document,
)


def _doc(*blocks: tuple[str, str]) -> DocumentModel:
    return DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"id": f"b{n}", "kind": kind, "text": text}
                        for n, (kind, text) in enumerate(blocks, 1)
                    ],
                }
            ],
        }
    )


DOC = _doc(("paragraph", "Wójt Gminy Elbląg. Wniosek o zezwolenie."))


def _f(fid: str, label: str, kind: str = "short_text", **extra: Any) -> dict[str, Any]:
    return {"id": fid, "label": label, "kind": kind, "required": True, **extra}


def _form(*sections: tuple[str, list[dict[str, Any]]], page: str = "Dane sprawy") -> FormDraft:
    return FormDraft.model_validate(
        {
            "title": "Wniosek o zezwolenie",
            "authority_kind": "ORGAN",
            "authority_name": "Wójt Gminy Elbląg",
            "applicant_kinds": ["SELF"],
            "subject_pages": [
                {
                    "title": page,
                    "sections": [
                        {"title": title, "repeating": False, "fields": fields}
                        for title, fields in sections
                    ],
                }
            ],
        }
    )


def _labels(draft: FormDraft) -> list[str]:
    return [f.label for _, f in draft.iter_fields()]


def _codes(warnings: list[Any]) -> list[str]:
    return [w.code for w in warnings]


# --- #3: data wypełnienia i podpisu ---


@pytest.mark.parametrize(
    ("label", "context"),
    [
        ("Data wypełnienia", ["Podpis"]),
        ("Data wypełnienia", ["Dane wniosku"]),
        ("Data wypełnienia i podpis", ["Oświadczenie"]),
        ("Data", ["Data i podpis"]),
        ("Dnia", ["Podpis wnioskodawcy"]),
        ("Data:", ["Dane", "Podpisy"]),
    ],
)
def test_signature_dates_detected(label: str, context: list[str]) -> None:
    assert applicant_field_reason(label, context)


@pytest.mark.parametrize(
    ("label", "context"),
    [
        ("Data", ["Termin wynajmu"]),
        ("Data urodzenia", ["Data i podpis"]),
        ("Data zdarzenia", ["Podpis"]),
        ("Data od", ["Podpis"]),
        ("Data rozpoczęcia", ["Dane"]),
        ("Termin", ["Data i podpis"]),
    ],
)
def test_subject_dates_kept(label: str, context: list[str]) -> None:
    assert applicant_field_reason(label, context) is None


def test_signature_date_removed_from_signature_section() -> None:
    draft = _form(
        ("Dane psa", [_f("f1", "Rasa psa")]),
        ("Data i podpis", [_f("f2", "Data", "date")]),
    )
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Rasa psa"]
    assert "W20_APPLICANT_FIELD_REMOVED" in _codes(warnings)


def test_lone_date_left_after_applicant_fields_removed() -> None:
    # Formularz 5: „Ulan-Majorat, dnia …” obok danych podatnika, które usuwa W20.
    draft = _form(
        ("Dane podatnika", [_f("f1", "Data", "date"), _f("f2", "PESEL"), _f("f3", "NIP")]),
        ("Nadpłata", [_f("f4", "Kwota nadpłaty", "number")]),
    )
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Kwota nadpłaty"]
    removed = [w.message for w in warnings if w.code == "W20_APPLICANT_FIELD_REMOVED"]
    assert (
        "Usunięto pole „Data”: miejsce i data złożenia oraz podpis są w sekcjach systemowych."
        in (removed)
    )


def test_date_among_other_fields_kept() -> None:
    draft = _form(("Szczepienie", [_f("f1", "Data", "date"), _f("f2", "Numer szczepionki")]))
    out, _ = normalize_draft(draft, DOC)
    assert _labels(out) == ["Data", "Numer szczepionki"]


@pytest.mark.parametrize("label", ["Data urodzenia", "Data zdarzenia", "Termin"])
def test_lone_subject_date_kept(label: str) -> None:
    out, _ = normalize_draft(_form(("Dane psa", [_f("f1", label, "date")])), DOC)
    assert _labels(out) == [label]


def test_lone_date_in_date_titled_section_kept() -> None:
    out, _ = normalize_draft(_form(("Termin wynajmu", [_f("f1", "Data", "date")])), DOC)
    assert _labels(out) == ["Data"]


# --- #5: pola opcjonalne ---


@pytest.mark.parametrize(
    "label",
    [
        "Numer telefonu (opcjonalnie)",
        "Adres e-mail - nieobowiązkowo",
        "Ewentualne dodatkowe informacje",
        "Numer lokalu (jeśli dotyczy)",
        "Numer KRS (jeżeli dotyczy)",
        "Nazwa szkoły (o ile dotyczy)",
        "NIP/REGON (dot. tylko osób prawnych)",
        "Numer KRS (dotyczy tylko spółek)",
        "Data szczepienia (w przypadku jego braku)",
        "Pochodzenie psa (hodowla, opcjonalnie)",
        "Numer licencji, o ile posiada",
        "Nazwa klubu, o ile jest członkiem",
    ],
)
def test_optional_fields_not_required(label: str) -> None:
    out, warnings = normalize_draft(_form(("Dane kandydata", [_f("f1", label)])), DOC)
    (field,) = (f for _, f in out.iter_fields())
    assert field.required is False
    assert field.label == label
    assert f"Pole „{label}” oznaczono jako niewymagane: na blankiecie jest opcjonalne." in [
        w.message for w in warnings if w.code == "W38_OPTIONAL_FIELD"
    ]


def test_optional_label_unchanged() -> None:
    out, _ = normalize_draft(
        _form(("Dane kandydata", [_f("f1", "Numer telefonu (opcjonalnie)")])), DOC
    )
    assert _labels(out) == ["Numer telefonu (opcjonalnie)"]


@pytest.mark.parametrize("label", ["Opis przypadku", "Uzasadnienie", "Numer telefonu"])
def test_required_fields_stay_required(label: str) -> None:
    out, warnings = normalize_draft(_form(("Dane kandydata", [_f("f1", label)])), DOC)
    assert all(f.required for _, f in out.iter_fields())
    assert "W38_OPTIONAL_FIELD" not in _codes(warnings)


def test_optional_info_and_already_optional_skipped() -> None:
    draft = _form(
        (
            "Dane psa",
            [
                _f("f1", "Rasa psa (opcjonalnie)", required=False),
                _f("f2", "Pola oznaczone jako opcjonalne można pominąć", "info"),
                _f("f3", "Imię psa"),
            ],
        )
    )
    _, warnings = normalize_draft(draft, DOC)
    assert "W38_OPTIONAL_FIELD" not in _codes(warnings)


# --- #6: pola bez etykiety ---


@pytest.mark.parametrize("label", ["2)", "3)", "-", "", "—", " … "])
def test_unlabeled_fields_removed(label: str) -> None:
    draft = _form(("Dane psa", [_f("f1", "Rasa psa"), _f("f2", label)]))
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Rasa psa"]
    assert any(
        w.code == "W39_UNLABELED_FIELD_REMOVED"
        and w.message == f"Usunięto pole bez etykiety „{label}”."
        and w.path == "subject_pages[0].sections[0].fields[1]"
        for w in warnings
    )


def test_unnamed_attachment_field_left_for_attachment_rule() -> None:
    draft = _form(("Załączniki", [_f("f1", "Rasa psa"), _f("f2", "2)", "file")]))
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Rasa psa"]
    assert "W26_UNNAMED_ATTACHMENT_REMOVED" in _codes(warnings)
    assert "W39_UNLABELED_FIELD_REMOVED" not in _codes(warnings)


@pytest.mark.parametrize("label", ["1. Imię", "A", "Nr 5 lokalu"])
def test_labeled_fields_kept(label: str) -> None:
    draft = _form(("Dane psa", [_f("f1", "Rasa psa"), _f("f2", label)]))
    _, warnings = normalize_draft(draft, DOC)
    assert "W39_UNLABELED_FIELD_REMOVED" not in _codes(warnings)


def test_condition_on_unlabeled_field_removed() -> None:
    draft = _form(
        (
            "Dane psa",
            [
                _f("f1", "-", "single_choice", options=["Tak", "Nie"]),
                _f(
                    "f2",
                    "Rasa psa",
                    visible_when=[{"field_id": "f1", "op": "equals", "value": "Tak"}],
                ),
            ],
        )
    )
    out, warnings = normalize_draft(draft, DOC)
    assert _labels(out) == ["Rasa psa"]
    assert all(not f.visible_when for _, f in out.iter_fields())
    assert "W21_CONDITION_REMOVED" in _codes(warnings)


# --- #11: oświadczenia ---


def test_statement_number_without_dot_stripped() -> None:
    doc = _doc(("paragraph", "1 Oświadczam, że psy nie będą wykorzystywane do polowań."))
    assert statements_from_document(doc) == [
        "Oświadczam, że psy nie będą wykorzystywane do polowań."
    ]


def test_statement_number_with_dot_still_stripped() -> None:
    doc = _doc(("paragraph", "1. Oświadczam, że dane są prawdziwe."))
    assert statements_from_document(doc) == ["Oświadczam, że dane są prawdziwe."]


def test_number_before_other_words_kept() -> None:
    doc = _doc(("paragraph", "Zobowiązuję się utrzymywać 2 psy w kojcu."))
    assert statements_from_document(doc) == ["Zobowiązuję się utrzymywać 2 psy w kojcu."]


def test_joined_statements_split() -> None:
    doc = _doc(
        (
            "paragraph",
            "2 Oświadczam, że psy nie będą wykorzystywane do polowań — 3 Oświadczam, że "
            "zapewniam warunki utrzymywania psa.",
        ),
        ("paragraph", "Oświadczam, że zapewniam warunki utrzymywania psa."),
    )
    assert statements_from_document(doc) == [
        "Oświadczam, że psy nie będą wykorzystywane do polowań",
        "Oświadczam, że zapewniam warunki utrzymywania psa.",
    ]


@pytest.mark.parametrize("separator", [" 3. ", " - 3) ", " \u2013 3 "])
def test_joined_statements_split_on_numbers(separator: str) -> None:
    doc = _doc(("paragraph", f"Oświadczam, że A{separator}Zobowiązuję się do B."))
    assert statements_from_document(doc) == ["Oświadczam, że A", "Zobowiązuję się do B."]


def test_numbered_items_after_colon_not_split() -> None:
    text = "Oświadczam, że: 1) zobowiązuję się do opieki, 2) zobowiązuję się do szczepień."
    assert statements_from_document(_doc(("paragraph", text))) == [
        "Oświadczam, że: zobowiązuję się do opieki, zobowiązuję się do szczepień."
    ]


def test_statement_with_number_inside_not_split() -> None:
    doc = _doc(("paragraph", "Oświadczam, że posiadam 2 psy, zobowiązuję się do opieki."))
    assert statements_from_document(doc) == [
        "Oświadczam, że posiadam 2 psy, zobowiązuję się do opieki."
    ]


def test_is_statement_with_number_without_dot() -> None:
    assert is_statement("1 Oświadczam, że wyrażam zgodę")
    assert is_statement("2. Oświadczam, że psy nie będą wykorzystywane do polowań")
    assert not is_statement("12 psów")


@pytest.mark.parametrize(
    "verb",
    [
        "zapoznałem się",
        "zapoznałam się",
        "zapoznałem/am się",
        "zapoznałem/łam się",
        "zapoznałem(-am) się",
        "zapoznała/em się",
        "zapoznałem / am się",
    ],
)
def test_acquaintance_statement_gender_neutral(verb: str) -> None:
    doc = _doc(("paragraph", f"Oświadczam, że {verb} z regulaminem."))
    assert statements_from_document(doc) == ["Potwierdzam zapoznanie się z regulaminem."]


def test_acquaintance_inside_sentence_unchanged() -> None:
    text = "Oświadczam, że akceptuję warunki oraz zapoznałem/am się z regulaminem."
    assert statements_from_document(_doc(("paragraph", text))) == [text]


def test_other_gendered_forms_unchanged() -> None:
    text = "Oświadczam, że zostałem poinformowany o zasadach."
    assert statements_from_document(_doc(("paragraph", text))) == [text]


def test_statement_after_position_number_still_a_field() -> None:
    doc = _doc(
        ("paragraph", "35."),
        ("paragraph", "Oświadczam, że zapoznałem się z regulaminem."),
        ("paragraph", "Oświadczam, że dane są prawdziwe."),
    )
    assert statements_from_document(doc) == ["Oświadczam, że dane są prawdziwe."]


def test_acquaintance_field_inside_listed_statement_still_removed() -> None:
    doc = _doc(
        ("paragraph", "Wójt Gminy Elbląg."),
        ("paragraph", "Jednocześnie oświadczam, że:"),
        ("paragraph", "zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej,"),
    )
    label = "Oświadczam, że zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej"
    draft = _form(("Oświadczenia", [_f("f1", label, "info"), _f("f2", "Rasa psa")]))
    out, warnings = normalize_draft(draft, doc)
    assert _labels(out) == ["Rasa psa"]
    assert "W17_STATEMENT_REMOVED" in _codes(warnings)


def test_acquaintance_field_still_removed_as_statement() -> None:
    doc = _doc(
        ("paragraph", "Wójt Gminy Elbląg."),
        (
            "paragraph",
            "Oświadczam, że zapoznałem się z regulaminem przyznawania stypendiów sportowych.",
        ),
    )
    draft = _form(
        (
            "Oświadczenia",
            [
                _f(
                    "f1",
                    "Oświadczam, że zapoznałem się z regulaminem przyznawania stypendiów "
                    "sportowych.",
                    "info",
                ),
                _f("f2", "Rasa psa"),
            ],
        )
    )
    out, warnings = normalize_draft(draft, doc)
    assert out.statements == [
        "Potwierdzam zapoznanie się z regulaminem przyznawania stypendiów sportowych."
    ]
    assert _labels(out) == ["Rasa psa"]
    assert "W17_STATEMENT_REMOVED" in _codes(warnings)
