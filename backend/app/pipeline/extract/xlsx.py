"""XLSX: openpyxl - komórki, scalenia, obramowania → geometria → silnik układu.

Blankiety w arkuszu rysują pola jako puste komórki z obramowaniem obok etykiety, a kratki
(NIP, kod pocztowy) jako ciągi wąskich kolumn. Pozycje komórek liczymy z szerokości kolumn
i wysokości wierszy, więc te same reguły co dla PDF rozpoznają pola i checkboxy.
"""

from itertools import accumulate
from typing import IO

import openpyxl
from openpyxl.cell.cell import Cell
from openpyxl.utils import column_index_from_string
from openpyxl.worksheet.dimensions import ColumnDimension
from openpyxl.worksheet.worksheet import Worksheet

from app.core.errors import AppError, ErrorCode
from app.models.document import BBox, DocumentModel
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.layout import Frame, Span, layout_page

COLUMN_WIDTH_PT = 5.6
"""Szerokość kolumny w openpyxl jest w znakach; ~5,6 pt na znak przy Calibri 11."""
DEFAULT_COLUMN_WIDTH = 8.43
DEFAULT_ROW_HEIGHT_PT = 15.0
MIN_BORDER_SIDES = 3
MAX_CELLS = 200_000
"""Ochrona przed arkuszami o ogromnym zakresie (`dimensions` z formatowania). Ten sam limit
dotyczy komórek zapisanych w pliku: blankiet ma ich najwyżej kilka tysięcy, więc 200 tys.
to duży zapas, a jednocześnie granica, przy której układ strony liczyłby się minutami."""


def extract_xlsx(file: IO[bytes]) -> DocumentModel:
    workbook = openpyxl.load_workbook(file, data_only=True)
    builder = DocumentBuilder("xlsx")
    try:
        # read_only odpada: arkusz w tym trybie nie ma column_dimensions ani scaleń.
        stored = sum(len(sheet._cells) for sheet in workbook.worksheets)
        if stored > MAX_CELLS:
            raise AppError(
                ErrorCode.DOCUMENT_TOO_COMPLEX,
                f"Arkusz ma {stored} komórek, dopuszczalne jest {MAX_CELLS}",
            )
        for sheet in workbook.worksheets:
            if sheet.sheet_state != "visible":
                continue
            spans, frames = _sheet_items(sheet)
            if spans:
                builder.new_page()
                layout_page(builder, spans, frames)
    finally:
        workbook.close()
    return builder.build()


def _sheet_items(sheet: Worksheet) -> tuple[list[Span], list[Frame]]:
    max_row, max_col = sheet.max_row, sheet.max_column
    if max_row * max_col > MAX_CELLS:
        max_row = max(1, MAX_CELLS // max(max_col, 1))
    columns = _column_dimensions(sheet, max_col)
    xs = _offsets([_column_width(sheet, columns.get(c)) for c in range(1, max_col + 1)])
    ys = _offsets([_row_height(sheet, r) for r in range(1, max_row + 1)])

    merged = {
        (rng.min_row, rng.min_col): (rng.min_row, rng.min_col, rng.max_row, rng.max_col)
        for rng in sheet.merged_cells.ranges
    }

    spans: list[Span] = []
    frames: list[Frame] = []
    for row_cells in sheet.iter_rows(min_row=1, max_row=max_row, max_col=max_col):
        for cell in row_cells:
            if not isinstance(cell, Cell):  # MergedCell: część scalonego zakresu
                continue
            row, col = cell.row, cell.column
            if _hidden(sheet, row, columns.get(col)):
                continue
            r0, c0, r1, c1 = merged.get((row, col), (row, col, row, col))
            r1, c1 = min(r1, max_row), min(c1, max_col)
            bbox = BBox(x0=xs[c0 - 1], y0=ys[r0 - 1], x1=xs[c1], y1=ys[r1])
            if bbox.x1 <= bbox.x0 or bbox.y1 <= bbox.y0:
                continue
            text = _text(cell.value)
            if text:
                font = cell.font
                size = float(font.sz) if font is not None and font.sz else None
                bold = bool(font is not None and font.b)
                spans.append(Span(text, bbox, bold=bold, size=size))
            elif _is_field(sheet, r0, c0, r1, c1, max_row):
                frames.append(Frame(bbox))
    return spans, frames


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def _is_field(sheet: Worksheet, r0: int, c0: int, r1: int, c1: int, max_row: int) -> bool:
    """Pusta komórka jest polem, gdy ma ramkę (≥ 3 krawędzie) albo podkreślenie (dół)."""

    def styled(row: int, col: int, side: str) -> bool:
        border = sheet.cell(row=row, column=col).border
        edge = getattr(border, side, None) if border is not None else None
        return bool(edge is not None and edge.style)

    bottom = styled(r1, c0, "bottom") or (r1 < max_row and styled(r1 + 1, c0, "top"))
    sides = sum((styled(r0, c0, "left"), styled(r0, c1, "right"), styled(r0, c0, "top"), bottom))
    return bottom or sides >= MIN_BORDER_SIDES


def _column_dimensions(sheet: Worksheet, max_col: int) -> dict[int, ColumnDimension]:
    """Numer kolumny → wymiar; `<col min max>` z pliku opisuje cały zakres kolumn naraz."""
    columns: dict[int, ColumnDimension] = {}
    for dim in sheet.column_dimensions.values():
        low = dim.min or column_index_from_string(dim.index)
        for col in range(low, min(dim.max or low, max_col) + 1):
            columns[col] = dim
    return columns


def _hidden(sheet: Worksheet, row: int, col_dim: ColumnDimension | None) -> bool:
    row_dim = sheet.row_dimensions.get(row)
    return bool(
        (row_dim is not None and row_dim.hidden) or (col_dim is not None and col_dim.hidden)
    )


def _column_width(sheet: Worksheet, dim: ColumnDimension | None) -> float:
    if dim is not None and dim.hidden:
        return 0.0
    width = dim.width if dim is not None and dim.width else _default_width(sheet)
    return float(width) * COLUMN_WIDTH_PT


def _default_width(sheet: Worksheet) -> float:
    fmt = sheet.sheet_format
    width = getattr(fmt, "defaultColWidth", None) or getattr(fmt, "baseColWidth", None)
    return float(width) if width else DEFAULT_COLUMN_WIDTH


def _row_height(sheet: Worksheet, row: int) -> float:
    dim = sheet.row_dimensions.get(row)
    if dim is not None and dim.hidden:
        return 0.0
    if dim is not None and dim.height:
        return float(dim.height)
    default = getattr(sheet.sheet_format, "defaultRowHeight", None)
    return float(default) if default else DEFAULT_ROW_HEIGHT_PT


def _offsets(sizes: list[float]) -> list[float]:
    """Pozycje krawędzi: offsets[i] to początek elementu i+1 (offsets[0] = 0)."""
    return [0.0, *accumulate(sizes)]
