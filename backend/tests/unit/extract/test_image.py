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


def drawn_page() -> io.BytesIO:
    """A4 w 200 DPI: ramka pola obok etykiety, kratka checkboxa, podkreślenie."""
    from PIL import ImageDraw

    image = Image.new("L", (1654, 2339), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((500, 200, 1400, 260), outline=0, width=3)  # pole obok „Miejscowość”
    draw.rectangle((150, 400, 185, 435), outline=0, width=3)  # kratka
    draw.line((500, 640, 1000, 640), fill=0, width=3)  # podkreślenie
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_frames_and_underlines_detected_from_pixels() -> None:
    engine = FakeOcr(
        [
            [
                word("Miejscowość", 150, 215, 300),
                word("Gotówką", 210, 405, 200),
                word("Ulica", 150, 605, 150),
            ]
        ]
    )
    doc, _ = extract_image(drawn_page(), engine, max_pages=30, check=no_check)
    assert kinds(doc) == [
        ("label", "Miejscowość"),
        ("input_placeholder", ""),
        ("checkbox_option", "Gotówką"),
        ("label", "Ulica"),
        ("input_placeholder", ""),
    ]


def test_text_strokes_are_not_lines() -> None:
    from PIL import ImageDraw, ImageFont

    image = Image.new("L", (1654, 400), 255)
    ImageDraw.Draw(image).text(
        (50, 50), "Wniosek o zwrot opłaty TTTT mmmm", fill=0, font=ImageFont.load_default(40)
    )
    from app.pipeline.extract.raster import frames_from_image

    assert frames_from_image(image, 200) == []


def test_dotted_leader_detected() -> None:
    from PIL import ImageDraw

    from app.pipeline.extract.raster import frames_from_image

    image = Image.new("L", (1654, 400), 255)
    draw = ImageDraw.Draw(image)
    for x in range(600, 1200, 9):
        draw.rectangle((x, 200, x + 2, 202), fill=0)
    frames = frames_from_image(image, 200)
    assert len(frames) == 1
    assert 600 * 72 / 200 - 5 < frames[0].x0 < 600 * 72 / 200 + 5
