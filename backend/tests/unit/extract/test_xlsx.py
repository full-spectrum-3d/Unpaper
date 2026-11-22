import io

import openpyxl
import pytest
from openpyxl.styles import Border, Font, Side

from app.models.document import DocumentModel
from app.pipeline.extract.xlsx import extract_xlsx
from tests.unit.extract.helpers import kinds

THIN = Side(style="thin")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def roundtrip(workbook: openpyxl.Workbook) -> DocumentModel:
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return extract_xlsx(buffer)


def boxed(sheet: object, cells: str) -> None:
    for row in sheet[cells]:  # type: ignore[index]
        for cell in row:
            cell.border = BOX


def test_label_and_bordered_merged_field() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.merge_cells("A1:B1")
    ws["A1"] = "Miejscowość"
    ws.merge_cells("C1:F1")
    boxed(ws, "C1:F1")
    assert kinds(roundtrip(wb)) == [("label", "Miejscowość"), ("input_placeholder", "")]


def test_comb_cells_one_field() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "NIP"
    for col in "BCDEFGHIJK":
        ws.column_dimensions[col].width = 2.5
    boxed(ws, "B1:K1")
    assert kinds(roundtrip(wb)) == [("label", "NIP"), ("input_placeholder", "")]


def test_underlined_cell_is_field() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "w obrębie"
    ws["B1"].border = Border(bottom=THIN)
    assert kinds(roundtrip(wb)) == [("label", "w obrębie"), ("input_placeholder", "")]


def test_bold_title_is_heading() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Dane wnioskodawcy"
    ws["A1"].font = Font(bold=True)
    ws["A3"] = "Zwykły tekst objaśnienia"
    assert kinds(roundtrip(wb)) == [
        ("heading", "Dane wnioskodawcy"),
        ("paragraph", "Zwykły tekst objaśnienia"),
    ]


def test_hidden_rows_and_sheets_skipped() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Widoczny"
    ws["A2"] = "Ukryty wiersz"
    ws.row_dimensions[2].hidden = True
    hidden = wb.create_sheet("Ukryty")
    hidden["A1"] = "Ukryty arkusz"
    hidden.sheet_state = "hidden"
    assert kinds(roundtrip(wb)) == [("paragraph", "Widoczny")]


def test_each_sheet_is_page() -> None:
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Pierwszy"
    wb.create_sheet("Pusty")
    wb.create_sheet("Drugi")["A1"] = "Drugi"
    doc = roundtrip(wb)
    assert [[b.text for b in page.blocks] for page in doc.pages] == [["Pierwszy"], ["Drugi"]]
    assert doc.source.method == "xlsx"


def test_numbers_as_text() -> None:
    wb = openpyxl.Workbook()
    wb.active["A1"] = 2024
    wb.active["A3"] = 12.5
    assert [b.text for b in roundtrip(wb).iter_blocks()] == ["2024", "12.5"]


def test_empty_workbook_has_one_empty_page() -> None:
    doc = roundtrip(openpyxl.Workbook())
    assert len(doc.pages) == 1 and doc.pages[0].blocks == []


def test_grouped_column_range_widths_and_hidden() -> None:
    # Plik zapisuje C:F jednym <col min=3 max=6>: wszystkie cztery kolumny są wąskie.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "NIP"
    ws.column_dimensions.group("B", "E", hidden=False)
    ws.column_dimensions["B"].width = 2.5
    ws.column_dimensions.group("G", "H", hidden=True)
    ws["H1"] = "ukryte"  # H leży w ukrytym zakresie G:H
    boxed(ws, "B1:E1")
    doc = roundtrip(wb)
    assert kinds(doc) == [("label", "NIP"), ("input_placeholder", "")]
    field = doc.pages[0].blocks[1].bbox
    assert field is not None and round(field.x1 - field.x0, 1) == round(4 * 2.5 * 5.6, 1)


def test_too_many_cells_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.errors import AppError, ErrorCode
    from app.pipeline.extract import xlsx

    wb = openpyxl.Workbook()
    ws = wb.active
    for row in range(1, 12):
        ws.cell(row=row, column=1, value="x")
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    monkeypatch.setattr(xlsx, "MAX_CELLS", 10)
    with pytest.raises(AppError) as exc:
        extract_xlsx(buffer)
    assert exc.value.code == ErrorCode.DOCUMENT_TOO_COMPLEX
