from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.text_rules import (
    is_fill_only,
    is_heading_style,
    looks_like_heading,
    split_checkbox_options,
)


def test_split_checkbox_options() -> None:
    assert split_checkbox_options(" Tak  Nie") == ["Tak", "Nie"]
    assert split_checkbox_options("  ☐ inne……") == ["inne……"]
    assert split_checkbox_options("Tak ☐") is None
    assert split_checkbox_options("☐") == []


def test_fill_only() -> None:
    assert is_fill_only("…………………. ")
    assert is_fill_only("(…….):")
    assert not is_fill_only("ulica ….")
    assert not is_fill_only("(adres)")


def test_heading_rules() -> None:
    def h(text: str, bold: bool = False, size: float = 10, alone: bool = True) -> bool:
        return looks_like_heading(text, bold=bold, size=size, body_size=10, alone=alone)

    assert h("WNIOSEK O USTALENIE NUMERU")
    assert h("2. Dane wnioskodawcy", bold=True)
    assert h("Wniosek o zwrot", size=14, alone=False)
    assert not h("2. Dane wnioskodawcy", bold=True, alone=False)
    assert not h("NIP ……………", bold=True, size=12)
    assert not h("PESEL")
    assert not h("X" * 151, bold=True, size=20)
    assert not h("ilości użytków", bold=True)
    assert not h("☐ TAK NIE WIEM", bold=True)


def test_heading_style() -> None:
    assert is_heading_style("Heading 1")
    assert is_heading_style("Nagłówek 2")
    assert is_heading_style("Title")
    assert not is_heading_style("Normal")
    assert not is_heading_style(None)


def test_builder_ids_and_trailing_empty_pages() -> None:
    builder = DocumentBuilder("pdf_text")
    builder.new_page()
    builder.add("heading", "A")
    builder.new_page()
    builder.add("paragraph", "B", confidence=1.2)
    builder.new_page()
    doc = builder.build()
    assert [p.number for p in doc.pages] == [1, 2]
    assert [b.id for b in doc.iter_blocks()] == ["b1", "b2"]
    assert doc.source.pages == 2
    assert doc.pages[1].blocks[0].ocr_confidence == 1.0


def test_builder_empty_document_has_one_page() -> None:
    doc = DocumentBuilder("xlsx").build()
    assert len(doc.pages) == 1
    assert doc.pages[0].blocks == []
