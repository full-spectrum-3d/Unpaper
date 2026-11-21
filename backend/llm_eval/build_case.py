"""Budowa przypadków pomiarowych prawdziwą ekstrakcją z produkcji (`app.pipeline.extract`).

Przypadek zapisujemy jako gotowy `DocumentModel`, a plik źródłowy kopiujemy do
`llm_eval/sources/`, żeby `document` dało się odtworzyć po zmianie ekstrakcji.

Uruchom z backend/:  uv run python -m llm_eval.build_case <plik> <slug> [--set cases|holdout]
"""

import argparse
import json
import shutil
from pathlib import Path

from app.core.config import Settings
from app.models.document import DocumentModel
from app.pipeline.extract import extract
from app.pipeline.normalize import NormalizedDocument
from app.pipeline.upload_validation.policy import EXTENSION_KINDS, FileKind

HERE = Path(__file__).parent
SOURCES = HERE / "sources"
_UNSUPPORTED = {"doc", "odt", "ods"}
_ALLOWED = {FileKind.PDF, FileKind.DOCX, FileKind.XLSX, FileKind.PNG, FileKind.JPEG}


def _kind(path: Path) -> FileKind:
    ext = path.suffix.lower().lstrip(".")
    if ext in _UNSUPPORTED:
        raise ValueError(f"{path.name}: format .{ext} nieobsługiwany, zapisz jako DOCX/XLSX")
    kind = EXTENSION_KINDS.get(ext)
    if kind not in _ALLOWED:
        raise ValueError(f"{path.name}: nieobsługiwane rozszerzenie .{ext}")
    return kind


def build_document(path: Path, settings: Settings) -> DocumentModel:
    """Plik → `DocumentModel` tą samą ekstrakcją co produkcja (OCR: Tesseract)."""
    kind = _kind(path)
    with path.open("rb") as file:
        result = extract(NormalizedDocument(kind=kind, file=file, converted=False), settings)
    return result.document


def build_case(path: Path, slug: str, settings: Settings, case_set: str = "cases") -> DocumentModel:
    """Zapisuje `document` i `source` przypadku; `expected` i `name` zostają, jeśli istnieją."""
    doc = build_document(path, settings)
    if not doc.to_prompt_text().strip():
        raise ValueError(f"{path.name}: ekstrakcja nie dała żadnej treści (skan bez Tesseracta?)")
    SOURCES.mkdir(exist_ok=True)
    stored = f"{slug}{path.suffix.lower()}"
    shutil.copyfile(path, SOURCES / stored)
    target = HERE / case_set / f"{slug}.json"
    target.parent.mkdir(exist_ok=True)
    case = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    case.update(name=case.get("name", path.stem), source=stored)
    case["document"] = doc.model_dump(mode="json", exclude_none=True)
    case.setdefault("expected", {"title": "", "authority_name": "", "fields": []})
    target.write_text(json.dumps(case, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("slug")
    parser.add_argument("--set", dest="case_set", choices=["cases", "holdout"], default="cases")
    args = parser.parse_args()
    settings = Settings(app_env="development", auth_enabled=False, _env_file=None)
    print(build_case(args.file, args.slug, settings, args.case_set).to_prompt_text())


if __name__ == "__main__":
    main()
