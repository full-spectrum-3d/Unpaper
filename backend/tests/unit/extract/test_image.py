import io

from PIL import Image

from app.pipeline.extract.image import extract_image, image_dpi, split_pages
from tests.unit.extract.fake_ocr import FakeOcr, word
from tests.unit.extract.helpers import kinds


def png(width: int, height: int, dpi: tuple[int, int] | None = None) -> io.BytesIO:
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), "white")
    if dpi:
        image.save(buffer, format="PNG", dpi=dpi)
    else:
        image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def no_check() -> None:
    return None


def test_split_pages() -> None:
    assert len(split_pages(Image.new("L", (100, 283)), 30)) == 2
    assert len(split_pages(Image.new("L", (100, 141)), 30)) == 1
    pages = split_pages(Image.new("L", (100, 2000)), 3)
    assert len(pages) == 3
    assert all(p.size[0] == 100 for p in pages)


def test_tall_image_ocr_per_page() -> None:
    engine = FakeOcr()
    doc, _ = extract_image(png(100, 283), engine, max_pages=30, check=no_check)
    assert engine.sizes == [(100, 142), (100, 141)]
    assert doc.source.method == "ocr"


def test_ocr_words_become_blocks() -> None:
    engine = FakeOcr(
        [
            [
                word("Imię", 100, 100, 80),
                word("i", 190, 100, 10),
                word("nazwisko", 210, 100, 140),
                word("……………", 100, 160, 300, conf=0.5),
            ]
        ]
    )
    doc, stats = extract_image(png(1654, 2339), engine, max_pages=30, check=no_check)
    assert kinds(doc) == [("label", "Imię i nazwisko"), ("input_placeholder", "")]
    assert doc.pages[0].blocks[0].ocr_confidence == 0.9
    assert stats.confidences[1] == (0.9 * 3 + 0.5) / 4


def test_dpi_from_metadata_scales_bbox() -> None:
    engine = FakeOcr([[word("Tekst", 100, 100)]])
    doc, _ = extract_image(png(800, 1100, dpi=(100, 100)), engine, max_pages=30, check=no_check)
    bbox = doc.pages[0].blocks[0].bbox
    assert bbox is not None and round(bbox.x0, 2) == 72.0


def test_dpi_without_metadata_assumes_a4_width() -> None:
    assert round(image_dpi(Image.new("L", (1654, 2339)))) == 200


def test_failed_page_recorded() -> None:
    doc, stats = extract_image(png(100, 141), FakeOcr(fail=True), max_pages=30, check=no_check)
    assert stats.failed == [1]
    assert doc.pages[0].blocks == []
