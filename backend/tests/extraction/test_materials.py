"""Ekstrakcja na blankietach z materiałów konkursu (spec §13.1).

Katalog z materiałami wskazuje `COI_MATERIALS_DIR` (np. rozpakowane „Wnioski”, po jednym
podkatalogu na formularz, nazwa zaczyna się numerem). Bez zmiennej test jest pomijany.
Pełna ścieżka pipeline'u: walidacja → normalizacja → ekstrakcja. DOC/ODS wymagają
LibreOffice (znacznik `converter`), obrazy - Tesseracta (znacznik `ocr`).
"""

import os
import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.pipeline.converter import find_converter
from app.pipeline.extract import extract
from app.pipeline.normalize import normalize
from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import UploadLimits
from app.pipeline.upload_validation.validate import validate_file

MATERIALS = os.environ.get("COI_MATERIALS_DIR")

EXPECTED: dict[str, list[str]] = {
    "1": ["numeru porządkowego", "ewidencyjny działki", "obrębie"],
    "2": ["Data uiszczenia opłaty", "Nr rachunku", "Gotówką w kasie organu"],
    "3": ["wydanie zaświadczenia", "użytków rolnych", "PESEL"],
    "4": ["świetlicy wiejskiej", "Przewidywana ilość uczestników", "Cel wynajęcia"],
    "5": ["nadpłaty", "rachunek", "Uzasadnienie"],
    "6": ["pasa drogowego", "nr ewid", "w celu"],
    "7": ["agresywne", "Imię i nazwisko", "Kod pocztowy"],
    "8": ["gospodarowanie odpadami", "Kod pocztowy", "Okoliczności"],
    "9": ["stypendium sportowego", "nagrody", "Rady Miasta Zgierza"],
}
OFFICE = {".pdf", ".docx", ".xlsx"}
CONVERTED = {".doc", ".ods"}
IMAGES = {".jpg", ".jpeg", ".png"}
_FORM_NUMBER = re.compile(r"^(\d+)\.")


def _materials() -> list[object]:
    if not MATERIALS:
        return [pytest.param(None, marks=pytest.mark.skip(reason="brak COI_MATERIALS_DIR"))]
    params: list[object] = []
    for path in sorted(Path(MATERIALS).rglob("*")):
        number = _FORM_NUMBER.match(path.parent.name)
        ext = path.suffix.lower()
        if not path.is_file() or not number or "wizualizacja" in path.name:
            continue
        marks = []
        if ext in CONVERTED:
            marks.append(pytest.mark.converter)
        elif ext in IMAGES:
            marks.append(pytest.mark.ocr)
        elif ext not in OFFICE:
            continue
        params.append(pytest.param(path, id=f"{number[1]}{ext}", marks=marks))
    return params


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


@pytest.mark.parametrize("path", _materials())
async def test_key_phrases_extracted(path: Path, tmp_path: Path) -> None:
    settings = Settings(app_env="development", auth_enabled=False, _env_file=None)  # type: ignore[call-arg]
    limits = UploadLimits()
    with path.open("rb") as handle:
        try:
            upload = validate_file(path.name, handle, limits)
        except UploadError as exc:
            # Materiały zawierają pliki odrzucane słusznie już przy walidacji (spec §6.3):
            # obraz ponad MAX_IMAGE_PIXELS i DOCX zapisany z rozszerzeniem .DOC.
            if exc.code in (UploadErrorCode.DOCUMENT_TOO_COMPLEX, UploadErrorCode.MIME_MISMATCH):
                pytest.skip(f"plik odrzucony przez walidację: {exc}")
            raise
        with upload:
            converter = find_converter(settings)
            if path.suffix.lower() in CONVERTED and converter is None:
                pytest.skip("brak soffice w PATH")
            with await normalize(upload, converter, limits, tmp_dir=str(tmp_path)) as doc:
                result = extract(doc, settings)

    number = _FORM_NUMBER.match(path.parent.name)
    assert number is not None
    text = _norm(result.document.to_prompt_text())
    found = [p for p in EXPECTED[number[1]] if _norm(p) in text]
    is_ocr = result.document.source.method == "ocr"
    # OCR gubi czasem polskie znaki - wystarczy jedna fraza; tekst cyfrowy musi mieć wszystkie.
    assert len(found) >= (1 if is_ocr else len(EXPECTED[number[1]])), (found, text[:500])
    assert "[pole]" in text or any(
        b.kind == "input_placeholder" for b in result.document.iter_blocks()
    )
