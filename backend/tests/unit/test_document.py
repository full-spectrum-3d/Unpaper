from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.document import DocumentModel

FIXTURE = Path(__file__).parent.parent / "fixtures" / "documents" / "wniosek1.json"


def _b(kind: str, text: str, **kw: Any) -> dict[str, Any]:
    return {"kind": kind, "text": text, **kw}


def _p(text: str) -> dict[str, Any]:
    return _b("paragraph", text)


def _h(text: str) -> dict[str, Any]:
    return _b("heading", text)


def _cell(row: int, col: int, text: str) -> dict[str, Any]:
    return _b("table_cell", text, table={"row": row, "col": col})


def _doc(*pages: list[dict[str, Any]]) -> DocumentModel:
    n = 0
    out_pages = []
    for number, blocks in enumerate(pages, 1):
        numbered = []
        for block in blocks:
            n += 1
            numbered.append({"id": f"b{n}", **block})
        out_pages.append({"number": number, "blocks": numbered})
    return DocumentModel.model_validate(
        {"source": {"method": "docx", "pages": len(pages)}, "pages": out_pages}
    )


def test_fill_runs_become_field_markers() -> None:
    doc = _doc([_p("w miejscowości……………….……………… przy ulicy1)…………")])
    assert doc.to_prompt_text() == "=== strona 1\nw miejscowości [POLE] przy ulicy1) [POLE]"


def test_markers_per_kind() -> None:
    doc = _doc([_h("Dane"), _b("checkbox_option", "Tak"), _b("input_placeholder", "....")])
    assert doc.to_prompt_text().splitlines()[1:] == ["[NAGŁÓWEK] Dane", "[OPCJA] Tak", "[POLE]"]


def test_table_rendering() -> None:
    doc = _doc(
        [
            _b("table", ""),
            _cell(0, 0, "Imię"),
            _cell(0, 1, ""),
            _cell(1, 0, "Nazwisko"),
            _cell(1, 1, ""),
            _p("Po tabeli"),
        ]
    )
    assert doc.to_prompt_text().splitlines()[1:] == [
        "[TABELA]",
        "Imię | ",
        "Nazwisko | ",
        "[/TABELA]",
        "Po tabeli",
    ]


def test_table_closed_at_page_end() -> None:
    doc = _doc([_b("table", ""), _cell(0, 0, "A")], [_p("B")])
    assert doc.to_prompt_text().splitlines() == [
        "=== strona 1", "[TABELA]", "A", "[/TABELA]", "=== strona 2", "B",
    ]  # fmt: skip


def test_gdpr_clause_excluded_until_next_heading() -> None:
    doc = _doc(
        [
            _p("Wnoszę o…"),
            _p("KLAUZULA INFORMACYJNA numeracja"),
            _p("Administratorem jest Gmina."),
        ],
        [_p("Inspektor danych…"), _h("Oświadczenia"), _p("Oświadczam, że…")],
    )
    text = doc.to_prompt_text()
    assert "Administratorem" not in text and "Inspektor" not in text
    assert "Oświadczam" in text and "Wnoszę" in text
    assert "Administratorem" in doc.to_prompt_text(exclude_boilerplate=False)


def test_wniosek1_fixture_prompt_is_compact() -> None:
    doc = DocumentModel.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    text = doc.to_prompt_text()
    assert "Wójt Gminy Elbląg" in text and "w obrębie [POLE]" in text
    assert "Inspektora Ochrony Danych" not in text
    assert len(text) < 1200


def test_duplicate_block_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="b1"):
        DocumentModel.model_validate(
            {
                "source": {"method": "docx", "pages": 1},
                "pages": [
                    {"number": 1, "blocks": [_p("a") | {"id": "b1"}, _p("b") | {"id": "b1"}]}
                ],
            }
        )


def test_table_cell_requires_position() -> None:
    with pytest.raises(ValidationError):
        _doc([_b("table_cell", "x")])


def test_ocr_mean_confidence() -> None:
    doc = _doc(
        [
            _b("paragraph", "a", ocr_confidence=0.5),
            _b("paragraph", "b"),
            _b("paragraph", "c", ocr_confidence=0.9),
        ]
    )
    assert doc.ocr_mean_confidence == pytest.approx(0.7)
    assert _doc([_p("a")]).ocr_mean_confidence is None


def test_passing_rodo_mention_does_not_drop_fields() -> None:
    doc = _doc([_p("Dane przetwarzamy zgodnie z RODO."), _p("Numer działki ………"), _p("Obręb ………")])
    text = doc.to_prompt_text()
    assert "Numer działki [POLE]" in text and "Obręb [POLE]" in text


def test_field_placeholder_ends_boilerplate_skip() -> None:
    doc = _doc([_p("KLAUZULA INFORMACYJNA"), _p("Administratorem…"), _p("Podpis ………")])
    text = doc.to_prompt_text()
    assert "Administratorem" not in text and "Podpis [POLE]" in text


def test_rodo_clause_starting_with_article_13_skipped() -> None:
    doc = DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"id": "b1", "kind": "paragraph", "text": "Cel: ………"},
                        {
                            "id": "b2",
                            "kind": "paragraph",
                            "text": "Zgodnie z art. 13 ust. 1 i 2 rozporządzenia Parlamentu "
                            "Europejskiego i Rady (UE) 2016/679 informujemy, że:",
                        },
                        {"id": "b3", "kind": "paragraph", "text": "Administratorem jest Wójt."},
                        {"id": "b4", "kind": "input_placeholder", "text": "……"},
                        {"id": "b5", "kind": "label", "text": "(podpis)"},
                    ],
                }
            ],
        }
    )
    assert doc.to_prompt_text() == "=== strona 1\nCel: [POLE]\n[POLE]\n(podpis)"


def test_rodo_heading_about_processing_your_data_skipped() -> None:
    doc = DocumentModel.model_validate(
        {
            "source": {"method": "pdf_text", "pages": 1},
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"id": "b1", "kind": "paragraph", "text": "Rasa psa: ………"},
                        {
                            "id": "b2",
                            "kind": "heading",
                            "text": "INFORMACJE DOTYCZĄCE PRZETWARZANIA TWOICH DANYCH OSOBOWYCH",
                        },
                        {
                            "id": "b3",
                            "kind": "paragraph",
                            "text": "Administratorem jest Prezydent.",
                        },
                    ],
                }
            ],
        }
    )
    assert doc.to_prompt_text() == "=== strona 1\nRasa psa: [POLE]"


def test_page_numbers_dropped() -> None:
    doc = _doc([_p("1/6"), _p("Wersja styczeń 2026 r. | Strona 1 z 2"), _p("strona 2/2"), _p("A")])
    assert doc.to_prompt_text() == "=== strona 1\nA"


@pytest.mark.parametrize(
    "start",
    [
        _p("Pouczenie:"),
        _p("Objaśnienia dotyczące sposobu wypełniania deklaracji"),
        _p("Informacja o przetwarzaniu danych osobowych"),
        _p("Stosownie do art. 13 i 14 Rozporządzenia Parlamentu Europejskiego"),
        _p("Obowiązek informacyjny"),
        _p("Zgodnie z rozporządzeniem Parlamentu Europejskiego i Rady (UE) 2016/679"),
        _h("I. ADNOTACJA ORGANU"),
        _h("Wypełnia urząd"),
    ],
)
def test_instructions_and_office_notes_skipped(start: dict[str, Any]) -> None:
    doc = _doc(
        [
            _p("Rasa psa ………"),
            start,
            _p("1. Deklarację należy wypełnić czytelnie."),
            _h("PESEL;"),
            _p("Administrator nie przewiduje profilowania."),
        ]
    )
    assert doc.to_prompt_text() == "=== strona 1\nRasa psa [POLE]"


def test_heading_after_instructions_resumes() -> None:
    doc = _doc(
        [_p("Pouczenie:"), _p("Opłatę wnosi się…"), _h("Dane nieruchomości"), _p("Obręb ………")]
    )
    assert doc.to_prompt_text().splitlines()[1:] == [
        "[NAGŁÓWEK] Dane nieruchomości",
        "Obręb [POLE]",
    ]


def test_repeated_fragment_collapsed() -> None:
    form = [
        _h("Dane klubu sportowego"),
        _p("Nazwa klubu ………"),
        _p("Telefon kontaktowy ………"),
        _p("Adres siedziby klubu sportowego ………"),
        _p("Skrzynka ePUAP - adres skrzynki: ………"),
    ]
    doc = _doc([_h("Wniosek o stypendium"), *form], [_h("Wniosek o nagrodę"), *form, _p("Inne")])
    lines = doc.to_prompt_text().splitlines()
    assert lines[-3:] == [
        "[NAGŁÓWEK] Wniosek o nagrodę",
        "[POWTÓRZENIE] fragment jak wyżej, od „[NAGŁÓWEK] Dane klubu sportowego”",
        "Inne",
    ]
    assert lines.count("Nazwa klubu [POLE]") == 1
    assert doc.to_prompt_text(collapse_repeats=False).count("Nazwa klubu [POLE]") == 2


def test_short_repeats_kept() -> None:
    doc = _doc(
        [_p("Imię ………"), _p("Nazwisko ………"), _h("Kandydat"), _p("Imię ………"), _p("Nazwisko ………")]
    )
    assert doc.to_prompt_text().count("Imię [POLE]") == 2


def test_fraction_in_table_cell_is_not_a_page_number() -> None:
    doc = _doc([_b("table", ""), _cell(0, 0, "Udział"), _cell(0, 1, "1/2")])
    assert "Udział | 1/2" in doc.to_prompt_text()
