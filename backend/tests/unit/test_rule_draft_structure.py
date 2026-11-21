"""Szkic z reguł: tytuły stron i sekcji, pliki przedmiotu, grupy wyboru z polami warunkowymi."""

from app.models.document import DocumentModel
from app.models.draft import FormDraft
from app.pipeline.rule_draft import rule_draft
from tests.unit.test_rule_draft import _doc


def _draft(doc: DocumentModel) -> FormDraft:
    draft = rule_draft(doc)
    assert draft is not None
    return draft


def _by_label(draft: FormDraft) -> dict[str, tuple[str, list[str], list[tuple[str, str]]]]:
    by_id = {f.id: f.label for _, f in draft.iter_fields()}
    return {
        f.label: (
            f.kind,
            f.options,
            [(by_id[c.field_id], c.value) for c in f.visible_when],
        )
        for _, f in draft.iter_fields()
    }


# --- E1: tytuły strony i sekcji ---------------------------------------------------------


def test_page_and_default_section_titled_from_request_subject() -> None:
    draft = _draft(
        _doc(
            ("heading", "WNIOSEK"),
            ("paragraph", "o stwierdzenie nadpłaty podatku"),
            ("paragraph", "w kwocie ………"),
        )
    )
    assert draft.subject_pages[0].title == "Stwierdzenie nadpłaty podatku"
    assert [s.title for s in draft.subject_pages[0].sections] == ["Stwierdzenie nadpłaty podatku"]


def test_section_title_taken_from_heading_over_the_fields() -> None:
    draft = _draft(
        _doc(
            ("heading", "WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO"),
            ("heading", "Lokalizacja budynku"),
            ("paragraph", "w miejscowości ………"),
        )
    )
    page = draft.subject_pages[0]
    assert page.title == "Ustalenie numeru porządkowego"
    assert [s.title for s in page.sections] == ["Lokalizacja budynku"]


def test_generic_titles_only_as_last_fallback() -> None:
    draft = _draft(_doc(("heading", "Zgłoszenie"), ("paragraph", "Nazwa ………")))
    assert draft.subject_pages[0].title == "Przedmiot wniosku"
    assert draft.subject_pages[0].sections[0].title == "Dane wniosku"


# --- E3: pliki przedmiotu sprawy --------------------------------------------------------


def test_file_listed_with_subject_stays_in_subject_section() -> None:
    draft = _draft(
        _doc(
            ("heading", "WNIOSEK"),
            ("paragraph", "o coś"),
            ("paragraph", "Kwota ………"),
            ("paragraph", "w załączeniu:"),
            ("paragraph", "1) korekta deklaracji"),
            ("paragraph", "2) ……………"),
        )
    )
    assert draft.attachments == []
    sections = {
        s.title: [(f.label, f.kind) for f in s.fields] for s in draft.subject_pages[0].sections
    }
    assert sections["Korekta deklaracji"] == [("Korekta deklaracji", "file")]
    assert all(f.required is False for _, f in draft.iter_fields() if f.kind == "file")


def test_explicit_attachment_list_goes_to_attachments() -> None:
    for header in ("Załączniki:", "Do wniosku dołączam:"):
        draft = _draft(
            _doc(
                ("heading", "WNIOSEK"),
                ("paragraph", "o coś"),
                ("paragraph", "Kwota ………"),
                ("paragraph", header),
                ("paragraph", "1) kopia umowy"),
                ("paragraph", "2) odpis z rejestru"),
            )
        )
        assert draft.attachments == ["Kopia umowy", "Odpis z rejestru"], header
        assert all(f.kind != "file" for _, f in draft.iter_fields())


# --- B4: grupy wyboru -------------------------------------------------------------------

CHECKBOXES = _doc(
    ("heading", "WNIOSEK"),
    ("paragraph", "o rozliczenie"),
    ("paragraph", "Kwota ………"),
    ("paragraph", "Sposób rozliczenia:"),
    ("paragraph", "☐ zaliczenie na poczet podatku ………"),
    ("paragraph", "☐ zwrot na rachunek nr ………"),
    ("paragraph", "☐ odbiór w kasie"),
    ("paragraph", "Uzasadnienie:"),
    ("input_placeholder", "……………"),
)


def test_checkbox_lines_become_single_choice_with_conditional_fields() -> None:
    by_label = _by_label(_draft(CHECKBOXES))
    assert by_label["Sposób rozliczenia"] == (
        "single_choice",
        ["Zaliczenie na poczet podatku", "Zwrot na rachunek", "Odbiór w kasie"],
        [],
    )
    assert by_label["Numer rachunku"][2] == [("Sposób rozliczenia", "Zwrot na rachunek")]
    assert by_label["Zaliczenie na poczet podatku"][2] == [
        ("Sposób rozliczenia", "Zaliczenie na poczet podatku")
    ]
    assert by_label["Uzasadnienie"][0] == "long_text"


def test_multi_choice_when_form_allows_several() -> None:
    doc = _doc(
        ("heading", "WNIOSEK"),
        ("paragraph", "o coś"),
        ("paragraph", "Kwota ………"),
        ("paragraph", "Zaznacz jedną lub więcej opcji:"),
        ("checkbox_option", "□ opcja A"),
        ("checkbox_option", "□ opcja B"),
    )
    assert _by_label(_draft(doc))["Zaznacz jedną lub więcej opcji"][0] == "multi_choice"


def test_single_checkbox_is_not_a_choice() -> None:
    doc = _doc(
        ("heading", "WNIOSEK"),
        ("paragraph", "o coś"),
        ("paragraph", "Kwota ………"),
        ("checkbox_option", "☐ zgadzam się"),
    )
    assert set(_by_label(_draft(doc))) == {"Kwota"}


NADPLATA_TAIL = (
    ("heading", "WNIOSEK"),
    ("paragraph", "o stwierdzenie nadpłaty podatku"),
    ("paragraph", "w kwocie ………"),
    ("paragraph", "Kwotę nadpłaty proszę:"),
    ("paragraph", "1) zaliczyć na poczet przyszłego zobowiązania podatkowego z tytułu ………"),
    ("input_placeholder", "……………"),
    ("paragraph", "2) zwrócić przelewem na wskazany rachunek"),
    ("table", ""),
    ("paragraph", "w załączeniu:"),
    ("paragraph", "1) korekta deklaracji"),
)


def test_numbered_options_under_request_intro_are_a_choice() -> None:
    by_label = _by_label(_draft(_doc(*NADPLATA_TAIL)))
    assert by_label["Kwotę nadpłaty"][0] == "single_choice"
    assert by_label["Tytuł"][2] == [
        ("Kwotę nadpłaty", "Zaliczyć na poczet przyszłego zobowiązania podatkowego")
    ]
    assert by_label["Numer rachunku"][2] == [
        ("Kwotę nadpłaty", "Zwrócić przelewem na wskazany rachunek")
    ]


def test_numbered_list_without_choice_intro_is_not_a_choice() -> None:
    doc = _doc(
        ("heading", "WNIOSEK"),
        ("paragraph", "o coś"),
        ("paragraph", "Dotychczasowe adresy:"),
        ("paragraph", "1) ulica ………"),
        ("paragraph", "2) miasto ………"),
    )
    assert all(kind != "single_choice" for kind, _, _ in _by_label(_draft(doc)).values())
