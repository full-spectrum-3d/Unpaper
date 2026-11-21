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
