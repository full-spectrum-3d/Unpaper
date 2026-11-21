"""Konwersja na prawdziwym LibreOffice: `uv run pytest -m converter tests/integration`.

Wymaga `soffice` w PATH i katalogu `materials/wniosek-1` (poza gitem). Porównuje tekst
DOC→DOCX i ODS→XLSX z oryginałami DOCX/XLSX tego samego wniosku.
"""

import asyncio
from pathlib import Path
from typing import IO

import docx
import openpyxl
import pytest

from app.core.config import Settings
from app.pipeline.converter import LibreOfficeConverter, find_converter
from app.pipeline.normalize import NormalizedDocument, normalize
from app.pipeline.upload_validation.policy import FileKind, UploadLimits
from app.pipeline.upload_validation.validate import validate_file

MATERIALS = Path(__file__).resolve().parents[3] / "materials" / "wniosek-1"
MIN_OVERLAP = 0.9

pytestmark = pytest.mark.converter


def _converter() -> LibreOfficeConverter:
    settings = Settings(app_env="development", auth_enabled=False, _env_file=None)  # type: ignore[call-arg]
    found = find_converter(settings)
    if found is None:
        pytest.skip("brak soffice w PATH")
    if not MATERIALS.is_dir():
        pytest.skip(f"brak {MATERIALS}")
    return found


def _material(ext: str) -> Path:
    matches = [p for p in MATERIALS.glob(f"*.{ext}") if "wizualizacja" not in p.name]
    assert len(matches) == 1, matches
    return matches[0]


def _clean(text: str) -> str:
    return " ".join(text.split())


def _docx_texts(file: IO[bytes] | Path) -> set[str]:
    document = docx.Document(file)  # type: ignore[arg-type]
    texts = [p.text for p in document.paragraphs]
    texts += [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    return {_clean(t) for t in texts if _clean(t)}


def _xlsx_texts(file: IO[bytes] | Path) -> set[str]:
    workbook = openpyxl.load_workbook(file, read_only=True, data_only=True)
    return {
        _clean(str(value))
        for sheet in workbook.worksheets
        for row in sheet.iter_rows(values_only=True)
        for value in row
        if value is not None and _clean(str(value))
    }


async def _normalize(ext: str, converter: LibreOfficeConverter, tmp: Path) -> NormalizedDocument:
    path = _material(ext)
    limits = UploadLimits()
    with path.open("rb") as handle:
        upload = validate_file(path.name, handle, limits)
        return await normalize(upload, converter, limits, tmp_dir=str(tmp))


def _overlap(expected: set[str], actual: set[str]) -> float:
    return len(expected & actual) / len(expected)


async def test_doc_to_docx_matches_original(tmp_path: Path) -> None:
    doc = await _normalize("doc", _converter(), tmp_path)
    with doc:
        assert doc.kind is FileKind.DOCX
        actual = _docx_texts(doc.file)
    assert _overlap(_docx_texts(_material("docx")), actual) >= MIN_OVERLAP
    assert list(tmp_path.iterdir()) == []


async def test_ods_to_xlsx_matches_original(tmp_path: Path) -> None:
    doc = await _normalize("ods", _converter(), tmp_path)
    with doc:
        assert doc.kind is FileKind.XLSX
        actual = _xlsx_texts(doc.file)
    assert _overlap(_xlsx_texts(_material("xlsx")), actual) >= MIN_OVERLAP
    assert list(tmp_path.iterdir()) == []


async def test_parallel_conversions(tmp_path: Path) -> None:
    converter = _converter()
    docs = await asyncio.gather(
        _normalize("doc", converter, tmp_path), _normalize("ods", converter, tmp_path)
    )
    assert [d.kind for d in docs] == [FileKind.DOCX, FileKind.XLSX]
    for doc in docs:
        doc.close()
