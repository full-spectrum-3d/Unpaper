from typing import Any

from app.models.document import DocumentModel
from app.pipeline.draft_normalize import normalize_draft
from app.pipeline.rule_draft import rule_draft


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


SWIETLICA = _doc(
    ("input_placeholder", "……………………"),
    ("label", "(imię i nazwisko wnioskodawcy)"),
    ("heading", "WÓJT GMINY PŁOSKINIA"),
    ("heading", "WNIOSEK"),
    ("paragraph", "o"),
    ("paragraph", "wynajęcie/użyczenie* świetlicy wiejskiej"),
    ("paragraph", "w terminie od ………… do …………"),
    ("paragraph", "Cel wynajęcia świetlicy: ……………"),
    ("paragraph", "Przewidywana ilość uczestników : ………"),
    ("heading", "3. Powierzchnia"),
    ("paragraph", "Całkowita powierzchnia zajęcia: ……… m2"),
    ("paragraph", "Uzasadnienie:"),
    ("input_placeholder", "……………………"),
    ("input_placeholder", "……………………"),
    ("paragraph", "w załączeniu:"),
    ("paragraph", "1) korekta deklaracji"),
    ("paragraph", "2) ……………"),
    ("input_placeholder", "……………………"),
    ("label", "(czytelny podpis wnioskodawcy)"),
)


def _fields(doc: DocumentModel) -> list[tuple[str, str, str]]:
    draft = rule_draft(doc)
    assert draft is not None
    draft, _ = normalize_draft(draft, doc)
    return [
        (section.title, f.label, f.kind)
        for page in draft.subject_pages
        for section in page.sections
        for f in section.fields
    ]


def test_fields_from_placeholders_skip_header_and_signature() -> None:
    assert _fields(SWIETLICA) == [
        ("Dane wniosku", "Termin", "date"),
        ("Dane wniosku", "W terminie do", "date"),
        ("Dane wniosku", "Cel wynajęcia świetlicy", "short_text"),
        ("Dane wniosku", "Przewidywana ilość uczestników", "number"),
        ("Powierzchnia", "Całkowita powierzchnia zajęcia (m2)", "number"),
        ("Powierzchnia", "Uzasadnienie", "long_text"),
    ]


def test_metadata_from_document() -> None:
    draft = rule_draft(SWIETLICA)
    assert draft is not None
    meta: dict[str, Any] = draft.model_dump(include={"title", "authority_kind", "authority_name"})
    assert meta == {
        "title": "Wniosek o wynajęcie/użyczenie świetlicy wiejskiej",
        "authority_kind": "ORGAN",
        "authority_name": "Wójt Gminy Płoskinia",
    }
    assert draft.attachments == ["Korekta deklaracji"]
    assert draft.applicant_kinds == ["SELF", "OTHER_PERSON"]


def test_office_name_joined_with_place_and_company_applicants() -> None:
    doc = _doc(
        ("paragraph", "Nazwisko i imię/Nazwa firmy"),
        ("paragraph", "Urząd Gminy"),
        ("paragraph", "Ulan-Majorat"),
        ("heading", "WNIOSEK"),
        ("paragraph", "o stwierdzenie nadpłaty"),
        ("paragraph", "w kwocie ………"),
    )
    draft = rule_draft(doc)
    assert draft is not None
    assert (draft.authority_kind, draft.authority_name) == ("URZAD", "Urząd Gminy Ulan-Majorat")
    assert draft.applicant_kinds == ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]
    assert _fields(doc) == [("Dane wniosku", "Kwota", "number")]


def test_no_placeholders_gives_none() -> None:
    assert rule_draft(_doc(("heading", "WNIOSEK"), ("paragraph", "Proszę o coś."))) is None
