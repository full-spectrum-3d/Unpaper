"""Prowizoryczna ekstrakcja DOCX/PDF → DocumentModel, tylko do budowy przypadków pomiarowych.

Prawdziwa ekstrakcja to `app/pipeline/extract/*` (dziś zaślepka). Przypadki zapisujemy
jako gotowy `DocumentModel`, więc pomiar nie zależy od zmian w ekstrakcji.

Uruchom z backend/:  uv run python -m llm_eval.extract <plik> <slug>
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

import docx
import pypdfium2 as pdfium
from docx.oxml.ns import qn
from lxml import etree  # type: ignore[import-untyped]

from app.models.document import Block, DocumentModel, Page, SourceInfo, TablePos

CASES = Path(__file__).parent / "cases"
_FILL = re.compile(r"^[\s.…_]+$")
_CHECKBOX = re.compile(r"[□☐■]")
_LABEL = re.compile(r"^\s*([(/]).*[)/]\s*$")
_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}


class _Blocks:
    def __init__(self) -> None:
        self.items: list[Block] = []

    def add(self, kind: str, text: str, **extra: Any) -> None:
        self.items.append(Block(id=f"b{len(self.items) + 1}", kind=kind, text=text, **extra))

    def text(self, text: str, heading: bool = False) -> None:
        text = text.strip()
        if not text:
            return
        if _FILL.match(text):
            self.add("input_placeholder", text)
        elif _CHECKBOX.match(text) or (len(_CHECKBOX.findall(text)) >= 2):
            for option in _CHECKBOX.split(text):
                if option.strip():
                    self.add("checkbox_option", option.strip())
        elif _LABEL.match(text):
            self.add("label", text)
        elif heading or (text.isupper() and len(text) < 80 and any(c.isalpha() for c in text)):
            self.add("heading", text)
        else:
            self.add("paragraph", text)


def _xpath(element: Any, expr: str) -> list[Any]:
    result: list[Any] = etree._Element.xpath(element, expr, namespaces=_NS)
    return result


def _para_text(p: Any) -> str:
    return "".join(t.text or "" for t in p.iter(qn("w:t")))


def _is_heading(p: Any) -> bool:
    style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    value = style.get(qn("w:val"), "") if style is not None else ""
    return value.lower().startswith(("heading", "nagwek", "nagłówek", "naglowek", "tytu"))


def extract_docx(path: Path) -> DocumentModel:
    document = docx.Document(str(path))
    out = _Blocks()
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            boxes = _xpath(child, ".//w:txbxContent[not(ancestor::mc:Fallback)]/w:p")
            if boxes:
                for p in boxes:
                    out.text(_para_text(p), _is_heading(p))
                continue
            out.text(
                "".join(t.text or "" for t in _xpath(child, "./w:r/w:t|./w:hyperlink/w:r/w:t")),
                _is_heading(child),
            )
        elif child.tag == qn("w:tbl"):
            out.add("table", "")
            for r, row in enumerate(child.iterchildren(qn("w:tr"))):
                for c, cell in enumerate(row.iterchildren(qn("w:tc"))):
                    text = " ".join(_para_text(p) for p in cell.iter(qn("w:p"))).strip()
                    if text:
                        out.add("table_cell", text, table=TablePos(row=r, col=c))
    return DocumentModel(
        source=SourceInfo(method="docx", pages=1), pages=[Page(number=1, blocks=out.items)]
    )


def extract_pdf(path: Path) -> DocumentModel:
    pdf = pdfium.PdfDocument(str(path))
    pages: list[Page] = []
    counter = 0
    for n, page in enumerate(pdf, 1):
        out = _Blocks()
        for line in page.get_textpage().get_text_range().splitlines():
            out.text(line)
        blocks = [
            b.model_copy(update={"id": f"b{counter + i + 1}"}) for i, b in enumerate(out.items)
        ]
        counter += len(blocks)
        pages.append(Page(number=n, blocks=blocks))
    return DocumentModel(source=SourceInfo(method="pdf_text", pages=len(pdf)), pages=pages)


def extract(path: Path) -> DocumentModel:
    return extract_pdf(path) if path.suffix.lower() == ".pdf" else extract_docx(path)


def main(path: Path, slug: str) -> None:
    doc = extract(path)
    target = CASES / f"{slug}.json"
    case = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    case.update(name=case.get("name", path.stem), source=path.name)
    case["document"] = doc.model_dump(mode="json", exclude_none=True)
    case.setdefault("expected", {"title": "", "authority_name": "", "fields": []})
    target.write_text(json.dumps(case, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(doc.to_prompt_text())


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
