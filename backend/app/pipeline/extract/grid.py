"""Odtwarzanie ramek z odcinków linii (kratki i pola rysowane kreskami).

Blankiety przekonwertowane z PDF rysują pola jako osobne cienkie linie. Komórki
wyznaczamy tak jak pdfplumber dla tabel: scalenie krawędzi, przecięcia, najmniejsze
prostokąty między przecięciami.
"""

from collections.abc import Sequence
from typing import Any

from pdfplumber.table import edges_to_intersections, intersections_to_cells, merge_edges

from app.models.document import BBox

THIN_PT = 2.5
"""Element o grubości ≤ 2,5 pt i długości większej niż grubość to odcinek linii."""
THICK_LINE_PT = 4.0
THICK_LINE_RATIO = 5.0
"""Grubsza kreska (≤ 4 pt) też jest linią, jeśli jest ≥ 5 razy dłuższa niż gruba."""
SNAP_PT = 3.0
MIN_CELL_PT = 8.0


def cells_from_segments(segments: Sequence[BBox]) -> list[BBox]:
    """Komórki ograniczone odcinkami poziomymi i pionowymi (współrzędne w pt, y w dół)."""
    edges: list[dict[str, Any]] = []
    for seg in segments:
        edges.extend(_edges_of(seg))
    if not edges:
        return []
    merged = merge_edges(edges, SNAP_PT, SNAP_PT, SNAP_PT, SNAP_PT)
    cells = intersections_to_cells(edges_to_intersections(merged, SNAP_PT, SNAP_PT))
    return [
        BBox(x0=float(x0), y0=float(top), x1=float(x1), y1=float(bottom))
        for x0, top, x1, bottom in cells
        if x1 - x0 >= MIN_CELL_PT and bottom - top >= MIN_CELL_PT
    ]


def _edges_of(seg: BBox) -> list[dict[str, Any]]:
    """Kreska → jej oś; prostokąt → cztery krawędzie; kropka → nic."""
    width, height = seg.x1 - seg.x0, seg.y1 - seg.y0
    thin, long = min(width, height), max(width, height)
    is_line = long > thin and (
        thin <= THIN_PT or (thin <= THICK_LINE_PT and long >= THICK_LINE_RATIO * thin)
    )
    if is_line and width > height:
        y = (seg.y0 + seg.y1) / 2
        return [_edge("h", seg.x0, seg.x1, y, y)]
    if is_line:
        x = (seg.x0 + seg.x1) / 2
        return [_edge("v", x, x, seg.y0, seg.y1)]
    if thin > THICK_LINE_PT:
        return rect_edges(seg)
    return []


def is_segment(box: BBox) -> bool:
    width, height = box.x1 - box.x0, box.y1 - box.y0
    return min(width, height) <= THIN_PT


def rect_edges(box: BBox) -> list[dict[str, Any]]:
    return [
        _edge("h", box.x0, box.x1, box.y0, box.y0),
        _edge("h", box.x0, box.x1, box.y1, box.y1),
        _edge("v", box.x0, box.x0, box.y0, box.y1),
        _edge("v", box.x1, box.x1, box.y0, box.y1),
    ]


def _edge(orientation: str, x0: float, x1: float, top: float, bottom: float) -> dict[str, Any]:
    return {
        "orientation": orientation,
        "object_type": "line",
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": bottom,
        "width": x1 - x0,
        "height": bottom - top,
    }
