"""DocumentModel - wynik ekstrakcji, niezależny od formatu (spec §5.3, projekt LLM §5.1).

`to_prompt_text()` zamienia dokument na zwięzły tekst z markerami dla LLM: wykropkowania
stają się `[POLE]`, a klauzula RODO jest pomijana (zgodę i tak dodaje szablon).
"""

import re
from collections.abc import Iterator
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

BlockKind = Literal[
    "heading", "paragraph", "label", "input_placeholder", "checkbox_option", "table", "table_cell"
]
ExtractionMethod = Literal["pdf_text", "ocr", "docx", "xlsx"]

FIELD_MARKER = "[POLE]"
_FILL_RUN = re.compile(r"[.…_]{3,}")
_WHITESPACE = re.compile(r"\s+")
_BOILERPLATE = re.compile(r"(?i)klauzula informacyjna|\bRODO\b|ochron\w* danych osobowych")


class _DocModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBox(_DocModel):
    x0: float
    y0: float
    x1: float
    y1: float


class TablePos(_DocModel):
    row: Annotated[int, Field(ge=0)]
    col: Annotated[int, Field(ge=0)]


class Block(_DocModel):
    id: str
    kind: BlockKind
    text: str
    bbox: BBox | None = None
    ocr_confidence: Annotated[float, Field(ge=0, le=1)] | None = None
    table: TablePos | None = None

    @model_validator(mode="after")
    def _cell_has_position(self) -> Self:
        if self.kind == "table_cell" and self.table is None:
            raise ValueError(f"blok {self.id}: table_cell wymaga pozycji `table`")
        return self


class Page(_DocModel):
    number: Annotated[int, Field(ge=1)]
    blocks: list[Block]


class SourceInfo(_DocModel):
    method: ExtractionMethod
    pages: Annotated[int, Field(ge=1)]


class DocumentModel(_DocModel):
    source: SourceInfo
    pages: list[Page]

    @model_validator(mode="after")
    def _unique_block_ids(self) -> Self:
        seen: set[str] = set()
        for block in self.iter_blocks():
            if block.id in seen:
                raise ValueError(f"id bloku {block.id} występuje więcej niż raz")
            seen.add(block.id)
        return self

    def iter_blocks(self) -> Iterator[Block]:
        for page in self.pages:
            yield from page.blocks

    @property
    def ocr_mean_confidence(self) -> float | None:
        values = [b.ocr_confidence for b in self.iter_blocks() if b.ocr_confidence is not None]
        return sum(values) / len(values) if values else None

    def to_prompt_text(self, exclude_boilerplate: bool = True) -> str:
        """Zwięzły tekst dokumentu z markerami `[NAGŁÓWEK]`, `[POLE]`, `[OPCJA]`, `[TABELA]`."""
        lines: list[str] = []
        skipping = False
        for page in self.pages:
            page_lines: list[str] = []
            table_rows: dict[int, list[tuple[int, str]]] | None = None
            for block in page.blocks:
                if exclude_boilerplate:
                    if block.kind in ("heading", "paragraph") and _BOILERPLATE.search(block.text):
                        skipping = True
                        continue
                    if skipping:
                        if block.kind != "heading":
                            continue
                        skipping = False
                if block.kind == "table_cell" and table_rows is not None and block.table:
                    table_rows.setdefault(block.table.row, []).append(
                        (block.table.col, _clean(block.text))
                    )
                    continue
                if table_rows is not None:
                    page_lines.extend(_render_table(table_rows))
                    table_rows = None
                if block.kind == "table":
                    table_rows = {}
                    continue
                page_lines.append(_render_block(block))
            if table_rows is not None:
                page_lines.extend(_render_table(table_rows))
            page_lines = [line for line in page_lines if line.strip()]
            if page_lines:
                lines.append(f"=== strona {page.number}")
                lines.extend(page_lines)
        return "\n".join(lines)


def _clean(text: str) -> str:
    text = _FILL_RUN.sub(f" {FIELD_MARKER} ", text)
    return _WHITESPACE.sub(" ", text).strip()


def _render_block(block: Block) -> str:
    match block.kind:
        case "heading":
            return f"[NAGŁÓWEK] {_clean(block.text)}"
        case "checkbox_option":
            return f"[OPCJA] {_clean(block.text)}"
        case "input_placeholder":
            return FIELD_MARKER
        case _:
            return _clean(block.text)


def _render_table(rows: dict[int, list[tuple[int, str]]]) -> list[str]:
    body = [" | ".join(text for _, text in sorted(rows[r])) for r in sorted(rows)]
    return ["[TABELA]", *body, "[/TABELA]"]
