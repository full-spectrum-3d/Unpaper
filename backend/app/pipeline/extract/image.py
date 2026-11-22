"""JPG/PNG (i skany stron PDF): preprocessing Pillow → OCR → silnik układu.

OCR jest za protokołem `OcrEngine`: w produkcji Tesseract (`pol`) przez pytesseract,
w testach atrapa. Obrazy z kilkoma stronami A4 sklejonymi w pionie dzielimy na strony.

Strona przechodzi dwa kroki. `read_page` (piksele i OCR, może działać w kilku wątkach naraz)
wymazuje wykropkowania, rozpoznaje tekst i wykrywa ramki. `place_page` (w wątku składającym
dokument, strona po stronie) układa z tego bloki.
"""

import math
import os
import re
import time
import warnings
from collections import deque
from collections.abc import Callable, Generator, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import IO, Protocol

import pytesseract
from PIL import Image, ImageOps

from app.models.document import BBox, DocumentModel
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.layout import Frame, Span, layout_page
from app.pipeline.extract.raster import detect_dotted, erase, frames_from_image
from app.pipeline.extract.text_rules import has_checkbox_glyph, is_fill_only

OCR_PAGE_TIMEOUT_S = 60
DEFAULT_IMAGE_DPI = 200.0
A4_WIDTH_IN = 8.27
PAGE_SPLIT_RATIO = 1.6
"""Obraz wyższy niż 1,6 szerokości to kilka stron A4 (proporcja √2) jedna pod drugą."""
MIN_METADATA_DPI = 150
"""Niższe DPI z metadanych to zwykle domyślne 72/96 aparatu lub telefonu, a nie skaner."""
TESSERACT_CONFIG = "--psm 11"
"""Tryb „tekst rozproszony”: blankiet to etykiety i pola, nie akapity. Tryb 3 gubił całe
regiony (nagłówek z datą, imieniem i PESEL). Kolejność czytania i tak wyznacza `layout`."""
TSV_LINE_LEVEL = 4
"""Poziom „linia” w wyniku `image_to_data`."""
OMP_THREADS_ENV = "OMP_THREAD_LIMIT"
"""Wątki OpenMP jednego procesu Tesseracta. Bez limitu kilka procesów naraz (strony
równolegle, dwa żądania) dławi się nawzajem: 4 strony trwały 36 s zamiast 4 s."""
REJECTED_CONFIDENCE = 0.1
"""Poniżej tej pewności Tesseract sam odrzucił słowo: to kratki i linie wzięte za litery."""
STRAY_MARK_CONFIDENCE = 0.5
"""Niepewny token bez liter i cyfr („|”, „=”) to krawędź ramki, nie znak z dokumentu."""
SURE_CONFIDENCE = 0.8
MISORIENTED_MIN_WORDS = 5
MISORIENTED_SURE_SHARE = 0.3
"""Strona leżąca na boku albo do góry nogami daje 6-14% pewnych słów, czytelna 40-90%."""
_WORD_CHAR = re.compile(r"\w")


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
    workers: int
    """Ile stron silnik może rozpoznawać jednocześnie."""

    def orient(self, image: Image.Image) -> Image.Image:
        """Obraz obrócony do pionu; ramki i rozmiar strony liczymy już z wyniku."""
        ...

    def recognize(self, image: Image.Image) -> list[OcrWord]: ...


@dataclass(slots=True)
class OcrStats:
    confidences: dict[int, float] = field(default_factory=dict)
    """Numer strony → średnia pewność OCR."""
    failed: list[int] = field(default_factory=list)
    """Strony, których OCR się nie udał."""


class TesseractOcr:
    def __init__(
        self,
        lang: str,
        timeout_s: float = OCR_PAGE_TIMEOUT_S,
        *,
        workers: int = 1,
        deadline: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.lang = lang
        self.timeout_s = timeout_s
        self.workers = workers
        self.deadline = deadline
        self.clock = clock
        self._osd: bool | None = None
        # pytesseract przekazuje procesowi Tesseracta środowisko tego procesu.
        os.environ.setdefault(OMP_THREADS_ENV, "1")

    def _timeout(self) -> float:
        """Limit wywołania Tesseracta: stały na stronę, ale nie dłuższy niż czas do deadline'u."""
        if self.deadline is None:
            return self.timeout_s
        remaining = self.deadline - self.clock()
        if remaining <= 0:  # timeout=0 w pytesseract oznacza brak limitu
            raise OcrUnavailableError("timeout")
        return min(self.timeout_s, remaining)

    def recognize(self, image: Image.Image) -> list[OcrWord]:
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=TESSERACT_CONFIG,
                output_type=pytesseract.Output.DICT,
                timeout=self._timeout(),
            )
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as exc:
            raise OcrUnavailableError(type(exc).__name__) from exc
        except RuntimeError as exc:  # pytesseract: „Tesseract process timeout”
            raise OcrUnavailableError("timeout") from exc
        return _words(data)

    def orient(self, image: Image.Image) -> Image.Image:
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
                image, output_type=pytesseract.Output.DICT, timeout=self._timeout()
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


@dataclass(frozen=True, slots=True)
class PageRead:
    """Wynik `read_page`: wszystko, czego `place_page` potrzebuje do ułożenia strony."""

    words: list[OcrWord]
    frames: list[BBox]
    """Ramki i pola nad podkreśleniami, w punktach."""
    dpi: float
    rotated: bool
    """Strona była obrócona o 90° - szerokość i wysokość zamienione."""


def read_page(image: Image.Image, engine: OcrEngine, dpi: float) -> PageRead | None:
    """Piksele strony → słowa i ramki; `None`, gdy OCR się nie udał.

    Orientację sprawdzamy dopiero po słabym odczycie: jej wykrywanie to 1,5-3 s na stronę,
    a prawie każdy skan jest już w pionie. Obróconą stronę czytamy drugi raz.
    """
    try:
        dotted = detect_dotted(image, dpi)
        words = engine.recognize(erase(image, dotted, dpi))
        rotated = False
        if _looks_misoriented(words):
            oriented = engine.orient(image)
            if oriented is not image:
                rotated = oriented.size != image.size
                image = oriented
                dotted = detect_dotted(image, dpi)
                words = engine.recognize(erase(image, dotted, dpi))
    except OcrUnavailableError:
        return None
    return PageRead(
        words=[w for w in words if not _is_noise(w)],
        frames=frames_from_image(image, dpi, dotted),
        dpi=dpi,
        rotated=rotated,
    )


def _looks_misoriented(words: list[OcrWord]) -> bool:
    texts = [w for w in words if _WORD_CHAR.search(w.text)]
    if len(texts) < MISORIENTED_MIN_WORDS:
        return False
    sure = sum(1 for w in texts if w.confidence >= SURE_CONFIDENCE)
    return sure < MISORIENTED_SURE_SHARE * len(texts)


def _is_noise(word: OcrWord) -> bool:
    """Token, którego nie ma w dokumencie: odrzucony przez OCR albo ślad linii.

    Wykropkowania i kratki zostają bez względu na pewność - `layout` robi z nich pola.
    """
    if is_fill_only(word.text) or has_checkbox_glyph(word.text):
        return False
    if word.confidence < REJECTED_CONFIDENCE:
        return True
    return not _WORD_CHAR.search(word.text) and word.confidence < STRAY_MARK_CONFIDENCE


def place_page(
    builder: DocumentBuilder, read: PageRead | None, number: int, stats: OcrStats
) -> None:
    """Układa odczytaną stronę na bieżącej stronie buildera i zapisuje statystyki.

    Nieudany OCR zostawia stronę pustą. Pewność strony to średnia ze słów: wykropkowania
    i znaki przestankowe jej nie zmieniają.
    """
    if read is None:
        stats.failed.append(number)
        return
    if read.rotated:
        builder.rotate_page()
    scale = 72.0 / read.dpi
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
        for word in read.words
    ]
    layout_page(builder, spans, [Frame(box) for box in read.frames])
    confidences = [w.confidence for w in read.words if _WORD_CHAR.search(w.text)]
    if confidences:
        stats.confidences[number] = sum(confidences) / len(confidences)


def read_ahead[T](jobs: Iterable[Callable[[], T]], workers: int) -> Generator[T]:
    """Wyniki `jobs` w kolejności zgłoszenia, liczone do `workers` naraz.

    `jobs` pobieramy leniwie, najwyżej o `workers` do przodu, więc w pamięci jest tylko
    kilka wyrenderowanych stron. Porzucenie iteratora anuluje zadania, które nie ruszyły.
    """
    if workers <= 1:
        for job in jobs:
            yield job()
        return
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr")
    pending: deque[Future[T]] = deque()
    try:
        for job in jobs:
            pending.append(pool.submit(job))
            if len(pending) >= workers:
                yield pending.popleft().result()
        while pending:
            yield pending.popleft().result()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def extract_image(
    file: IO[bytes], engine: OcrEngine, *, max_pages: int, check: Callable[[], None]
) -> tuple[DocumentModel, OcrStats]:
    builder = DocumentBuilder("ocr")
    stats = OcrStats()
    with warnings.catch_warnings():
        # Limit pikseli egzekwuje walidacja (MAX_IMAGE_PIXELS), nie domyślny próg Pillow.
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(file) as original:
            if original.format == "JPEG":
                # Dekodowanie od razu w skali szarości: 1 bajt na piksel zamiast 3.
                original.draft("L", original.size)
            original.load()
            prepared = preprocess(original)
    dpi = image_dpi(prepared)  # po obrocie EXIF: szerokość to już szerokość strony
    pages = split_pages(prepared, max_pages)
    del prepared
    scale = 72.0 / dpi
    jobs = (read_job(page, engine, dpi) for page in pages)
    reads = read_ahead(jobs, engine.workers)
    try:
        for number, page in enumerate(pages, start=1):
            check()
            builder.new_page((page.size[0] * scale, page.size[1] * scale))
            place_page(builder, next(reads), number, stats)
    finally:
        reads.close()
    return builder.build(), stats


def read_job(image: Image.Image, engine: OcrEngine, dpi: float) -> Callable[[], PageRead | None]:
    """`read_page` do wykonania później, z obrazem związanym już teraz."""
    return lambda: read_page(image, engine, dpi)
