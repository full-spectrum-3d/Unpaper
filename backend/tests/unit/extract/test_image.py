import io

import pytest
from PIL import Image

from app.pipeline.extract.image import OcrWord, extract_image, image_dpi, split_pages
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
    # Wykropkowanie to miejsce na wpis, nie tekst: nie obniża pewności strony.
    assert stats.confidences[1] == pytest.approx(0.9)


def test_rejected_and_stray_tokens_are_dropped() -> None:
    engine = FakeOcr(
        [
            [
                word("Rodzaj", 100, 100, 100),
                word("EEE", 220, 100, 60, conf=0.0),  # kratki odczytane jako litery
                word("|", 300, 100, 5, conf=0.3),  # krawędź ramki
                word("tak", 100, 200, 50),
                word("/", 160, 200, 10, conf=0.9),
                word("nie", 180, 200, 50),
            ]
        ]
    )
    doc, stats = extract_image(png(1654, 2339), engine, max_pages=30, check=no_check)
    assert [b.text for b in doc.pages[0].blocks] == ["Rodzaj", "tak / nie"]
    assert stats.confidences[1] == pytest.approx(0.9)


def test_dotted_leaders_are_erased_before_ocr() -> None:
    from PIL import ImageDraw

    image = Image.new("L", (1654, 400), 255)
    draw = ImageDraw.Draw(image)
    for x in range(600, 1200, 9):
        draw.rectangle((x, 200, x + 2, 202), fill=0)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    engine = FakeOcr()
    doc, _ = extract_image(buffer, engine, max_pages=30, check=no_check)
    seen = engine.images[0]
    assert all(seen.getpixel((x, 201)) == 255 for x in range(600, 1200))
    assert kinds(doc) == [("input_placeholder", "")]


def test_erasing_dots_keeps_the_word_they_follow() -> None:
    # „nazwisko.........”: pas kropek zaczyna się pod ostatnimi literami słowa.
    from PIL import ImageDraw

    from app.pipeline.extract.raster import detect_dotted, erase

    image = Image.new("L", (1654, 400), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((560, 172, 590, 202), fill=0)  # litera stojąca na linii kropek
    for x in range(600, 1200, 9):
        draw.rectangle((x, 200, x + 2, 202), fill=0)
    dotted = detect_dotted(image, 200)
    assert dotted and dotted[0][0] < 590  # wykryty pas obejmuje literę
    cleaned = erase(image, dotted, 200)
    assert all(cleaned.getpixel((x, 201)) == 0 for x in range(560, 591))
    assert all(cleaned.getpixel((x, 201)) == 255 for x in range(600, 1200))


def test_pages_are_read_in_parallel_and_kept_in_order() -> None:
    import threading

    class TwoAtOnce(FakeOcr):
        def __init__(self) -> None:
            super().__init__()
            self.workers = 2
            self.together = threading.Barrier(2, timeout=5)

        def recognize(self, image: Image.Image) -> list[OcrWord]:
            self.together.wait()  # przy czytaniu strona po stronie nikt nie dołączy
            return [word(f"wysokosc{image.size[1]}", 10, 10)]

    doc, _ = extract_image(png(100, 283), TwoAtOnce(), max_pages=30, check=no_check)
    assert [[b.text for b in p.blocks] for p in doc.pages] == [["wysokosc142"], ["wysokosc141"]]


def test_read_ahead_keeps_order_and_bounds_lookahead() -> None:
    from app.pipeline.extract.image import read_ahead

    started: list[int] = []

    def jobs():  # type: ignore[no-untyped-def]
        for n in range(6):
            started.append(n)
            yield lambda n=n: n * 10

    results = read_ahead(jobs(), 2)
    assert next(results) == 0
    assert len(started) <= 3  # strony renderujemy najwyżej o `workers` do przodu
    assert list(results) == [10, 20, 30, 40, 50]


def test_tesseract_runs_one_thread_per_page(monkeypatch: pytest.MonkeyPatch) -> None:
    # Kilka procesów Tesseracta z domyślnymi wątkami OpenMP dławi się nawzajem.
    import os

    from app.pipeline.extract.image import TesseractOcr

    monkeypatch.delenv("OMP_THREAD_LIMIT", raising=False)
    assert TesseractOcr("pol", workers=3).workers == 3
    assert os.environ["OMP_THREAD_LIMIT"] == "1"
    monkeypatch.setenv("OMP_THREAD_LIMIT", "2")
    TesseractOcr("pol")
    assert os.environ["OMP_THREAD_LIMIT"] == "2"


def test_dpi_from_metadata_scales_bbox() -> None:
    engine = FakeOcr([[word("Tekst", 300, 100)]])
    doc, _ = extract_image(png(800, 1100, dpi=(300, 300)), engine, max_pages=30, check=no_check)
    bbox = doc.pages[0].blocks[0].bbox
    assert bbox is not None and round(bbox.x0, 2) == 72.0


def test_dpi_without_metadata_assumes_a4_width() -> None:
    assert round(image_dpi(Image.new("L", (1654, 2339)))) == 200


def test_camera_default_dpi_ignored() -> None:
    for dpi in (72, 96, 100):
        image = Image.new("L", (1654, 2339))
        image.info["dpi"] = (dpi, dpi)
        assert round(image_dpi(image)) == 200


def test_dpi_guessed_after_exif_rotation() -> None:
    # Zdjęcie w poziomie z EXIF „obróć o 90°”: szerokość strony to krótszy bok.
    image = Image.new("RGB", (2339, 1654), "white")
    exif = image.getexif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    buffer.seek(0)
    doc, _ = extract_image(buffer, FakeOcr(), max_pages=30, check=no_check)
    page = doc.pages[0]
    assert page.width is not None and page.height is not None
    assert (round(page.width), round(page.height)) == (595, 842)


def unreadable(count: int = 6) -> list[OcrWord]:
    """Tak wygląda odczyt strony leżącej na boku: dużo słów, żadnego pewnego."""
    return [word("xq", 10, 10 + 40 * i, conf=0.2) for i in range(count)]


def test_osd_rotation_applies_to_page_size_and_frames() -> None:
    # Skan leży na boku; silnik obraca go do pionu - strona i ramki w układzie obróconym.
    from PIL import ImageDraw

    image = Image.new("L", (2339, 1654), 255)
    ImageDraw.Draw(image).rectangle((200, 500, 260, 1400), outline=0, width=3)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", dpi=(200, 200))
    buffer.seek(0)
    engine = FakeOcr([unreadable(), [word("Miejscowość", 20, 215, 200)]], rotate=-90)
    doc, _ = extract_image(buffer, engine, max_pages=30, check=no_check)
    page = doc.pages[0]
    assert engine.sizes == [(2339, 1654), (1654, 2339)]
    assert page.width is not None and page.height is not None
    assert page.width < page.height
    assert ("input_placeholder", "") in kinds(doc)
    assert [b.text for b in page.blocks if b.text] == ["Miejscowość"]


def test_orientation_is_checked_only_after_a_poor_read() -> None:
    # Wykrywanie orientacji kosztuje 1,5-3 s na stronę; czytelna strona go nie potrzebuje.
    engine = FakeOcr([[word("Miejscowość", 20, 215, 200)]], rotate=-90)
    doc, _ = extract_image(png(1654, 2339), engine, max_pages=30, check=no_check)
    assert engine.orient_calls == 0
    assert [b.text for b in doc.pages[0].blocks] == ["Miejscowość"]


def test_poor_read_of_an_upright_page_is_kept() -> None:
    engine = FakeOcr([unreadable()])
    _, stats = extract_image(png(1654, 2339), engine, max_pages=30, check=no_check)
    assert engine.orient_calls == 1
    assert len(engine.sizes) == 1
    assert stats.confidences[1] == pytest.approx(0.2)


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


def test_small_print_is_not_a_dotted_leader() -> None:
    # Wiersz drobnego druku po ściśnięciu wygląda jak pas kropek; od wykropkowania różni go
    # grubość: litery mają kilkanaście pikseli, kropki kilka.
    from PIL import ImageDraw, ImageFont

    from app.pipeline.extract.raster import detect_dotted

    image = Image.new("L", (2480, 300), 255)
    ImageDraw.Draw(image).text(
        (100, 100),
        "ustawy z dnia 20 czerwca 1997 r. prawo o ruchu drogowym oraz kodeks",
        fill=0,
        font=ImageFont.load_default(22),
    )
    assert detect_dotted(image, 300) == []


def test_page_size_matches_bbox_units() -> None:
    # 288 dpi to 4 piksele na punkt: strona 800 na 400 px ma 200 na 100 pt.
    doc, _ = extract_image(png(800, 400, dpi=(288, 288)), FakeOcr(), max_pages=30, check=no_check)
    page = doc.pages[0]
    assert page.width is not None and page.height is not None
    # PNG zapisuje rozdzielczość w pikselach na metr, stąd niewielkie zaokrąglenie.
    assert (round(page.width), round(page.height)) == (200, 100)


def test_tesseract_timeout_capped_by_deadline() -> None:
    import pytest

    from app.pipeline.extract.image import OcrUnavailableError, TesseractOcr

    now = [100.0]
    ocr = TesseractOcr("pol", deadline=110.0, clock=lambda: now[0])
    assert ocr._timeout() == 10.0
    now[0] = 30.0
    assert ocr._timeout() == 60
    now[0] = 111.0
    with pytest.raises(OcrUnavailableError):
        ocr._timeout()
    assert TesseractOcr("pol")._timeout() == 60
