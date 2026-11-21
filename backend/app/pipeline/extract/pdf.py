"""PDF: pdfplumber (słowa ze współrzędnymi, linie, tabele, AcroForm); skan → pypdfium2 → OCR.

Decyzja tekst/OCR zapada per strona: blankiet bywa sklejony ze stron tekstowych i skanów.
Pola to puste komórki z siatki linii (kratki, ramki), checkboxy to kwadratowe komórki albo
glify Wingdings w tekście. Siatka z tekstem w kilku komórkach to tabela.
"""

import io
import math
import re
from collections.abc import Callable
from typing import IO, Any

import pdfplumber
import pypdfium2 as pdfium
from pdfplumber.page import Page as PlumberPage
from PIL import Image

from app.models.document import BBox, DocumentModel
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.grid import cells_from_segments
from app.pipeline.extract.image import OcrEngine, OcrStats, preprocess, run_ocr
from app.pipeline.extract.layout import Frame, Span, TableGrid, layout_page
from app.pipeline.pdfium_lock import PDFIUM_LOCK

MIN_TEXT_CHARS = 20
"""Strona z mniejszą liczbą znaków (bez białych) to skan."""
MIN_TABLE_TEXT_CELLS = 2
LAYOUT_GRID_AREA_RATIO = 0.4
DATA_CELL_MAX_CHARS = 60
TABLE_SETTINGS: dict[str, Any] = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}
_BOLD_FONT = re.compile(r"(?i)bold|black|heavy|semibold|demi")


def extract_pdf(
    file: IO[bytes],
    engine: OcrEngine,
    *,
    dpi: int,
    max_pixels: int,
    check: Callable[[], None],
) -> tuple[DocumentModel, OcrStats]:
    file.seek(0)
    data = file.read()
    builder = DocumentBuilder("pdf_text")
    stats = OcrStats()
    used_ocr = False
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            check()
            builder.new_page()
            if _text_chars(page) >= MIN_TEXT_CHARS:
                _text_page(builder, page)
                continue
            used_ocr = True
            image, scale = _render(data, number - 1, dpi, max_pixels)
            run_ocr(builder, preprocess(image), engine, scale * 72, number, stats)
    if used_ocr:
        builder.method = "ocr"
    return builder.build(), stats


def render_scale(width_pt: float, height_pt: float, dpi: int, max_pixels: int) -> float:
    """Skala rasteryzacji: `dpi`/72, obniżona tak, by obraz miał ≤ `max_pixels` pikseli."""
    scale = dpi / 72
    area = width_pt * height_pt
    if area > 0 and area * scale * scale > max_pixels:
        scale = math.sqrt(max_pixels / area)
    return scale


def _text_chars(page: PlumberPage) -> int:
    return sum(1 for char in page.chars if not str(char.get("text", "")).isspace())


def _text_page(builder: DocumentBuilder, page: PlumberPage) -> None:
    words = page.extract_words(extra_attrs=["fontname", "size"])
    tables: list[TableGrid] = []
    frames: list[Frame] = []
    taken: list[BBox] = []
    for table in page.find_tables(TABLE_SETTINGS):
        cells = [_box(cell) for cell in table.cells]
        texts = [_text_in(words, cell) for cell in cells]
        grid = _grid(table.rows)
        table_box = _box(table.bbox)
        if _is_data_table(grid, texts, table_box, page):
            cell_texts = [
                (grid.row_of(cell), grid.col_of(cell), text)
                for cell, text in zip(cells, texts, strict=True)
            ]
            tables.append(TableGrid(table_box, cell_texts))
            taken.append(table_box)
    outlines = [_box((o["x0"], o["top"], o["x1"], o["bottom"])) for o in (*page.rects, *page.lines)]
    for cell in cells_from_segments(outlines):
        if not any(_overlaps(cell, box) for box in taken):
            frames.append(Frame(cell))
    frames.extend(_widgets(page))
    spans = [
        Span(
            str(w["text"]),
            BBox(x0=w["x0"], y0=w["top"], x1=w["x1"], y1=w["bottom"]),
            bold=bool(_BOLD_FONT.search(str(w.get("fontname", "")))),
            size=float(w["size"]) if w.get("size") else None,
        )
        for w in words
        if not any(_center_in(w, box) for box in taken)
    ]
    layout_page(builder, spans, frames, tables)


def _is_data_table(grid: _Grid, texts: list[str], box: BBox, page: PlumberPage) -> bool:
    """Tabela z danymi, a nie siatka układu strony (cały blankiet narysowany liniami).

    Siatkę układu poznać po tym, że zajmuje dużą część strony albo ma w komórkach długie
    teksty (opisy, pouczenia) - wtedy lepiej czytać ją jak zwykłą stronę z ramkami.
    """
    filled = [text for text in texts if text]
    if len(grid.rows) < 2 or len(grid.cols) < 2 or len(filled) < MIN_TABLE_TEXT_CELLS:
        return False
    area = (box.x1 - box.x0) * (box.y1 - box.y0)
    if area > LAYOUT_GRID_AREA_RATIO * float(page.width) * float(page.height):
        return False
    return sum(len(text) for text in filled) / len(filled) <= DATA_CELL_MAX_CHARS


class _Grid:
    """Indeksy wierszy i kolumn tabeli z krawędzi komórek."""

    def __init__(self, rows: list[float], cols: list[float]) -> None:
        self.rows = rows
        self.cols = cols

    def row_of(self, cell: BBox) -> int:
        return _nearest(self.rows, cell.y0)

    def col_of(self, cell: BBox) -> int:
        return _nearest(self.cols, cell.x0)


def _grid(rows: Any) -> _Grid:
    tops = sorted({round(row.bbox[1], 1) for row in rows})
    lefts = sorted({round(cell[0], 1) for row in rows for cell in row.cells if cell is not None})
    return _Grid(tops, lefts)


def _nearest(edges: list[float], value: float) -> int:
    return min(range(len(edges)), key=lambda i: abs(edges[i] - value)) if edges else 0


def _widgets(page: PlumberPage) -> list[Frame]:
    """Pola formularza AcroForm (tekstowe i checkboxy) jako ramki."""
    frames: list[Frame] = []
    for annot in page.annots or []:
        subtype = str((annot.get("data") or {}).get("Subtype", ""))
        if subtype.endswith("Widget'") or subtype.endswith("Widget"):
            frames.append(
                Frame(BBox(x0=annot["x0"], y0=annot["top"], x1=annot["x1"], y1=annot["bottom"]))
            )
    return frames


def _render(data: bytes, index: int, dpi: int, max_pixels: int) -> tuple[Image.Image, float]:
    with PDFIUM_LOCK:
        document = pdfium.PdfDocument(data)
        try:
            page = document[index]
            try:
                width, height = page.get_size()
                scale = render_scale(width, height, dpi, max_pixels)
                bitmap = page.render(scale=scale, grayscale=True)
                try:
                    image: Image.Image = bitmap.to_pil()
                    image.load()
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            document.close()
    return image, scale


def _text_in(words: list[dict[str, Any]], cell: BBox) -> str:
    return " ".join(str(w["text"]) for w in words if _center_in(w, cell))


def _center_in(word: dict[str, Any], box: BBox) -> bool:
    x = (word["x0"] + word["x1"]) / 2
    y = (word["top"] + word["bottom"]) / 2
    return bool(box.x0 <= x <= box.x1 and box.y0 <= y <= box.y1)


def _overlaps(a: BBox, b: BBox) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def _box(values: Any) -> BBox:
    x0, top, x1, bottom = values
    return BBox(x0=float(x0), y0=float(top), x1=float(x1), y1=float(bottom))
