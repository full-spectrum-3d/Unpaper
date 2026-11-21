"""Linie z obrazu strony (skan, zdjęcie): ramki pól, kratki, podkreślenia.

OCR zwraca tylko tekst - ramek i podkreśleń nie widzi. Szukamy ich bezpośrednio
w pikselach: poziome i pionowe ciągi ciemnych pikseli dłuższe niż litera. Szukanie ciągów
robi `re` na bajtach wiersza (w C), więc strona A4 w 200 DPI to ułamek sekundy.
"""

import re
from collections.abc import Iterator

from PIL import Image

from app.models.document import BBox
from app.pipeline.extract.grid import cells_from_segments

DARK_LEVEL = 128
MIN_LINE_IN = 0.12
"""Minimalna długość linii: ~8,6 pt - krawędź kratki checkboxa, dłuższa niż kreski liter."""
MERGE_SLACK_PX = 3
UNDERLINE_MIN_PT = 30.0
UNDERLINE_MAX_RATIO = 0.6
"""Dłuższe linie (≥ 60% szerokości strony) to separatory sekcji, nie pola."""
UNDERLINE_FIELD_PT = 12.0
"""Wysokość pola nad podkreśleniem."""
CELL_EDGE_PT = 3.0
DOT_SQUASH_IN = 1 / 16
"""Ściśnięcie w poziomie (~12 px w 200 DPI, więcej niż odstęp kropek) skleja wykropkowanie."""
DOT_DARK_LEVEL = 20
DOT_CLEAR_IN = 0.03
"""Wykropkowanie jest cienkie: ~6 px nad i pod nim musi być pusto (tekst tak nie wygląda)."""
DOT_CLEAR_MAX_SHARE = 0.2


def frames_from_image(image: Image.Image, dpi: float) -> list[BBox]:
    """Ramki (komórki z linii) i pola nad podkreśleniami, w punktach."""
    scale = 72.0 / dpi
    min_len = max(8, round(dpi * MIN_LINE_IN))
    segments = [
        BBox(x0=x0 * scale, y0=y0 * scale, x1=x1 * scale, y1=y1 * scale)
        for x0, y0, x1, y1 in detect_lines(image, min_len)
    ]
    dotted = [
        BBox(x0=x0 * scale, y0=y0 * scale, x1=x1 * scale, y1=y1 * scale)
        for x0, y0, x1, y1 in detect_dotted(image, dpi)
    ]
    cells = cells_from_segments(segments)
    page_width = image.size[0] * scale
    return cells + _dedupe(_underlines([*segments, *dotted], cells, page_width))


def _dedupe(boxes: list[BBox]) -> list[BBox]:
    """Ciągła linia trafia i do linii, i do wykropkowań - zostawiamy jedno pole."""
    out: list[BBox] = []
    for box in sorted(boxes, key=lambda b: b.x1 - b.x0, reverse=True):
        if not any(_overlap_share(box, kept) > 0.5 for kept in out):
            out.append(box)
    return out


def _overlap_share(a: BBox, b: BBox) -> float:
    width = min(a.x1, b.x1) - max(a.x0, b.x0)
    height = min(a.y1, b.y1) - max(a.y0, b.y0)
    if width <= 0 or height <= 0:
        return 0.0
    return width * height / ((a.x1 - a.x0) * (a.y1 - a.y0))


def detect_lines(image: Image.Image, min_len: int) -> list[tuple[int, int, int, int]]:
    """Odcinki (x0, y0, x1, y1) w pikselach: poziome i pionowe, sąsiednie wiersze scalone."""
    binary = image.convert("L").point(lambda v: 255 if v < DARK_LEVEL else 0)
    horizontal = _merge(_runs(binary, min_len))
    transposed = binary.transpose(Image.Transpose.TRANSPOSE)
    vertical = [(y0, x0, y1, x1) for x0, y0, x1, y1 in _merge(_runs(transposed, min_len))]
    return horizontal + vertical


def detect_dotted(image: Image.Image, dpi: float) -> list[tuple[int, int, int, int]]:
    """Wykropkowania i podkreślenia przerywane (x0, y0, x1, y1) w pikselach.

    OCR je zwykle pomija, a to w blankietach najczęstszy znak pola do wypełnienia.
    """
    factor = max(2, round(dpi * DOT_SQUASH_IN))
    binary = image.convert("L").point(lambda v: 255 if v < DARK_LEVEL else 0)
    width, height = binary.size
    if width < factor:
        return []
    squashed = binary.resize((width // factor, height), Image.Resampling.BOX)
    dense = squashed.point(lambda v: 255 if v >= DOT_DARK_LEVEL else 0)
    row_width = dense.size[0]
    data = dense.tobytes()
    gap = max(2, round(dpi * DOT_CLEAR_IN))
    min_len = max(2, round(UNDERLINE_MIN_PT / 72 * dpi / factor))

    def clear(y: int, x0: int, x1: int) -> bool:
        if not 0 <= y < height:
            return True
        row = data[y * row_width + x0 : y * row_width + x1]
        return row.count(255) <= DOT_CLEAR_MAX_SHARE * len(row)

    thin = (
        (y, x0, x1)
        for y, x0, x1 in _runs(dense, min_len)
        if clear(y - gap, x0, x1) and clear(y + gap, x0, x1)
    )
    return [(x0 * factor, y0, x1 * factor, y1) for x0, y0, x1, y1 in _merge(thin)]


def _runs(binary: Image.Image, min_len: int) -> Iterator[tuple[int, int, int]]:
    """(y, x0, x1) ciągów ciemnych pikseli w wierszach."""
    width, height = binary.size
    data = binary.tobytes()
    pattern = re.compile(b"\xff{%d,}" % min_len)
    for y in range(height):
        for match in pattern.finditer(data, y * width, (y + 1) * width):
            yield y, match.start() - y * width, match.end() - y * width


def _merge(runs: Iterator[tuple[int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Ciągi w kolejnych wierszach o tych samych końcach (gruba linia) → jeden odcinek."""
    active: dict[tuple[int, int], list[int]] = {}
    done: list[tuple[int, int, int, int]] = []
    for y, x0, x1 in runs:
        key = (x0 // MERGE_SLACK_PX, x1 // MERGE_SLACK_PX)
        seg = active.get(key)
        if seg is not None and seg[3] >= y - 1:
            seg[3] = y + 1
            seg[0], seg[2] = min(seg[0], x0), max(seg[2], x1)
            continue
        if seg is not None:
            done.append((seg[0], seg[1], seg[2], seg[3]))
        active[key] = [x0, y, x1, y + 1]
    done.extend((s[0], s[1], s[2], s[3]) for s in active.values())
    return done


def _underlines(segments: list[BBox], cells: list[BBox], page_width: float) -> list[BBox]:
    """Poziome linie, które nie są krawędzią komórki, jako pola tekstowe nad nimi."""
    out: list[BBox] = []
    for seg in segments:
        length = seg.x1 - seg.x0
        if seg.y1 - seg.y0 > length or not (
            UNDERLINE_MIN_PT <= length <= UNDERLINE_MAX_RATIO * page_width
        ):
            continue
        y = (seg.y0 + seg.y1) / 2
        if any(_on_cell_edge(seg, y, cell) for cell in cells):
            continue
        out.append(BBox(x0=seg.x0, y0=y - UNDERLINE_FIELD_PT, x1=seg.x1, y1=y))
    return out


def _on_cell_edge(seg: BBox, y: float, cell: BBox) -> bool:
    overlaps = seg.x0 < cell.x1 and cell.x0 < seg.x1
    near = abs(y - cell.y0) <= CELL_EDGE_PT or abs(y - cell.y1) <= CELL_EDGE_PT
    return overlaps and near
