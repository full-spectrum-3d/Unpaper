"""JPG/PNG (i skany stron PDF): preprocessing Pillow → OCR → silnik układu.

OCR jest za protokołem `OcrEngine`: w produkcji Tesseract (`pol`) przez pytesseract,
w testach atrapa. Obrazy z kilkoma stronami A4 sklejonymi w pionie dzielimy na strony.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import IO, Protocol

import pytesseract
from PIL import Image, ImageOps

from app.models.document import BBox, DocumentModel
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.layout import Frame, Span, layout_page
from app.pipeline.extract.raster import frames_from_image

OCR_PAGE_TIMEOUT_S = 60
DEFAULT_IMAGE_DPI = 200.0
A4_WIDTH_IN = 8.27
PAGE_SPLIT_RATIO = 1.6
"""Obraz wyższy niż 1,6 szerokości to kilka stron A4 (proporcja √2) jedna pod drugą."""
MIN_METADATA_DPI = 50
TESSERACT_CONFIG = "--psm 3"
TSV_LINE_LEVEL = 4
"""Poziom „linia” w wyniku `image_to_data`."""


@dataclass(frozen=True, slots=True)
class OcrWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    """Od 0 do 1."""
    line_height: int | None = None
    """Wysokość linii, w której leży słowo - stabilniejsza miara rozmiaru pisma."""


class OcrUnavailableError(Exception):
    """Silnik OCR nie jest zainstalowany albo zawiódł na stronie."""


class OcrEngine(Protocol):
    def recognize(self, image: Image.Image) -> list[OcrWord]: ...


@dataclass(slots=True)
class OcrStats:
    confidences: dict[int, float] = field(default_factory=dict)
    """Numer strony → średnia pewność OCR."""
    failed: list[int] = field(default_factory=list)
    """Strony, których OCR się nie udał."""


class TesseractOcr:
    def __init__(self, lang: str, timeout_s: float = OCR_PAGE_TIMEOUT_S) -> None:
        self.lang = lang
        self.timeout_s = timeout_s
        self._osd: bool | None = None

    def recognize(self, image: Image.Image) -> list[OcrWord]:
        try:
            image = self._orient(image)
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=TESSERACT_CONFIG,
                output_type=pytesseract.Output.DICT,
                timeout=self.timeout_s,
            )
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as exc:
            raise OcrUnavailableError(type(exc).__name__) from exc
        except RuntimeError as exc:  # pytesseract: „Tesseract process timeout”
            raise OcrUnavailableError("timeout") from exc
        return _words(data)

    def _orient(self, image: Image.Image) -> Image.Image:
        """Obrót według Tesseract OSD; bez danych `osd` albo przy błędzie - bez zmian."""
        if self._osd is None:
            try:
                self._osd = "osd" in pytesseract.get_languages(config="")
            except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as exc:
                raise OcrUnavailableError(type(exc).__name__) from exc
        if not self._osd:
            return image
        try:
            osd = pytesseract.image_to_osd(
                image, output_type=pytesseract.Output.DICT, timeout=self.timeout_s
            )
        except pytesseract.TesseractError, RuntimeError:
            return image
        rotate = int(osd.get("rotate", 0) or 0)
        return image.rotate(-rotate, expand=True) if rotate % 360 else image


def _words(data: dict[str, list[object]]) -> list[OcrWord]:
    lines: dict[tuple[object, ...], int] = {}
    for i, level in enumerate(data["level"]):
        if level == TSV_LINE_LEVEL:
            lines[_line_key(data, i)] = int(str(data["height"][i]))
    words: list[OcrWord] = []
    for i, raw in enumerate(data["text"]):
        text = str(raw).strip()
        conf = float(str(data["conf"][i]))
        if not text or conf < 0:
            continue
        words.append(
            OcrWord(
                text=text,
                left=int(str(data["left"][i])),
                top=int(str(data["top"][i])),
                width=int(str(data["width"][i])),
                height=int(str(data["height"][i])),
                confidence=min(conf, 100.0) / 100,
                line_height=lines.get(_line_key(data, i)),
            )
        )
    return words


def _line_key(data: dict[str, list[object]], i: int) -> tuple[object, ...]:
    return (data["page_num"][i], data["block_num"][i], data["par_num"][i], data["line_num"][i])


def preprocess(image: Image.Image) -> Image.Image:
    """Orientacja z EXIF, skala szarości, autokontrast."""
    image = ImageOps.exif_transpose(image) or image
    return ImageOps.autocontrast(image.convert("L"))


def split_pages(image: Image.Image, max_pages: int) -> list[Image.Image]:
    width, height = image.size
    if width <= 0 or height <= PAGE_SPLIT_RATIO * width:
        return [image]
    count = min(max(1, round(height / (width * math.sqrt(2)))), max_pages)
    step = math.ceil(height / count)
    return [image.crop((0, top, width, min(top + step, height))) for top in range(0, height, step)][
        :count
    ]


def image_dpi(image: Image.Image) -> float:
    """DPI z metadanych; bez nich zakładamy, że szerokość obrazu to szerokość A4."""
    dpi = image.info.get("dpi")
    if isinstance(dpi, tuple) and dpi and float(dpi[0]) >= MIN_METADATA_DPI:
        return float(dpi[0])
    width = image.size[0]
    return width / A4_WIDTH_IN if width else DEFAULT_IMAGE_DPI


def ocr_page(
    builder: DocumentBuilder, image: Image.Image, engine: OcrEngine, dpi: float
) -> float | None:
    """OCR jednej strony do bieżącej strony buildera; zwraca średnią pewność.

    Ramki i podkreślenia wykrywamy z pikseli - OCR ich nie zwraca.
    """
    scale = 72.0 / dpi
    spans = [
        Span(
            word.text,
            BBox(
                x0=word.left * scale,
                y0=word.top * scale,
                x1=(word.left + word.width) * scale,
                y1=(word.top + word.height) * scale,
            ),
            confidence=word.confidence,
            # Wysokość z OCR jest zbyt szumna na regułę rozmiaru nagłówka - zostają wersaliki.
            size=None,
        )
        for word in engine.recognize(image)
    ]
    frames = [Frame(box) for box in frames_from_image(image, dpi)]
    layout_page(builder, spans, frames)
    if not spans:
        return None
    return sum(s.confidence or 0.0 for s in spans) / len(spans)


def extract_image(
    file: IO[bytes], engine: OcrEngine, *, max_pages: int, check: Callable[[], None]
) -> tuple[DocumentModel, OcrStats]:
    builder = DocumentBuilder("ocr")
    stats = OcrStats()
    with Image.open(file) as original:
        original.load()
        dpi = image_dpi(original)
        prepared = preprocess(original)
    for number, page in enumerate(split_pages(prepared, max_pages), start=1):
        check()
        builder.new_page()
        run_ocr(builder, page, engine, dpi, number, stats)
    return builder.build(), stats


def run_ocr(
    builder: DocumentBuilder,
    image: Image.Image,
    engine: OcrEngine,
    dpi: float,
    number: int,
    stats: OcrStats,
) -> None:
    """`ocr_page` z zapisem statystyk; nieudany OCR zostawia stronę pustą."""
    try:
        confidence = ocr_page(builder, image, engine, dpi)
    except OcrUnavailableError:
        stats.failed.append(number)
        return
    if confidence is not None:
        stats.confidences[number] = confidence
