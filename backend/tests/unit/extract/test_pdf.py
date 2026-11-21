import io

from app.pipeline.extract.pdf import extract_pdf, render_scale
from tests.unit.extract.fake_ocr import FakeOcr, word
from tests.unit.extract.helpers import kinds
from tests.unit.extract.pdfgen import PdfPage, make_pdf


def run(pages: list[PdfPage], engine: FakeOcr | None = None):  # type: ignore[no-untyped-def]
    return extract_pdf(
        io.BytesIO(make_pdf(pages)),
        engine or FakeOcr(),
        dpi=150,
        max_pixels=60_000_000,
        check=lambda: None,
    )


def test_text_page_with_frame_field() -> None:
    page = PdfPage().text(50, 100, "Miejscowosc wnioskodawcy").rect(200, 95, 500, 117)
    doc, _ = run([page])
    assert kinds(doc) == [("label", "Miejscowosc wnioskodawcy"), ("input_placeholder", "")]
    assert doc.source.method == "pdf_text"


def test_bold_font_heading() -> None:
    page = PdfPage().text(50, 100, "2. Dane wnioskodawcy", bold=True)
    page.text(50, 130, "Zwykly tekst objasnienia pod naglowkiem formularza")
    doc, _ = run([page])
    assert kinds(doc)[0] == ("heading", "2. Dane wnioskodawcy")


def test_square_frame_checkbox() -> None:
    page = PdfPage().text(50, 60, "Sposob zwrotu oplaty skarbowej")
    page.rect(50, 100, 62, 112).text(70, 101, "Gotowka w kasie organu")
    doc, _ = run([page])
    assert ("checkbox_option", "Gotowka w kasie organu") in kinds(doc)


def test_text_table() -> None:
    page = PdfPage().text(50, 50, "Wykaz zalacznikow do wniosku o zwrot")
    for row in range(2):
        for col in range(2):
            page.rect(50 + 150 * col, 100 + 20 * row, 200 + 150 * col, 120 + 20 * row)
    for (row, col), text in {(0, 0): "Lp", (0, 1): "Nazwa", (1, 0): "1", (1, 1): "Dowod"}.items():
        page.text(55 + 150 * col, 104 + 20 * row, text)
    doc, _ = run([page])
    cells = [(b.table.row, b.table.col, b.text) for b in doc.iter_blocks() if b.table]
    assert cells == [(0, 0, "Lp"), (0, 1, "Nazwa"), (1, 0, "1"), (1, 1, "Dowod")]


def test_scanned_page_goes_to_ocr() -> None:
    text_page = PdfPage().text(50, 100, "Strona z warstwa tekstu i trescia")
    engine = FakeOcr([[word("Skan", 100, 100)]])
    doc, stats = run([text_page, PdfPage(scanned=True)], engine)
    assert len(engine.sizes) == 1
    width, height = engine.sizes[0]
    assert abs(width - 595 * 150 / 72) <= 1 and abs(height - 842 * 150 / 72) <= 1
    assert [[b.text for b in p.blocks] for p in doc.pages] == [
        ["Strona z warstwa tekstu i trescia"],
        ["Skan"],
    ]
    assert doc.source.method == "ocr"
    assert 2 in stats.confidences


def test_render_scale_capped() -> None:
    assert render_scale(595, 842, 300, 60_000_000) == 300 / 72
    a0 = render_scale(2384, 3370, 300, 60_000_000)
    assert 2384 * 3370 * a0 * a0 <= 60_000_000 * 1.0001
