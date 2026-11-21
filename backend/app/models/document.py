"""DocumentModel - wynik ekstrakcji, niezależny od formatu (spec §5.3, projekt LLM §5.1).

`to_prompt_text()` zamienia dokument na zwięzły tekst z markerami dla LLM: wykropkowania
stają się `[POLE]`, a klauzula RODO, pouczenia, objaśnienia wypełniania, adnotacje organu
i numery stron są pomijane (nie dają pól formularza, a zajmują większość długich blankietów).
Powtórzony fragment (np. trzy wnioski w jednym pliku) zastępuje znacznik `[POWTÓRZENIE]`.
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
_BOILERPLATE = re.compile(
    r"(?i)klauzula informacyjna|\bRODO\b|ochron\w* danych osobowych"
    r"|przetwarzani\w* (twoich |pani/pana |pana/pani )?danych osobowych"
    r"|^\W*([a-z0-9]{1,2}[.)]\s*)?(pouczeni|objaśnieni|instrukcj\w* wypełni)"
    r"|adnotacj\w* (organu|urzędu)|wypełnia (organ|urząd|pracownik)"
)
_BOILERPLATE_PARAGRAPH = re.compile(
    r"(?i)^\W*([a-z0-9]{1,2}[.)]\s*)?(klauzula informacyjna"
    r"|informacj\w* (o|dotycząc\w*) przetwarzani\w* (twoich |pani/pana |pana/pani )?danych"
    r"|(zgodnie z|stosownie do) art\. ?13\b"
    r"|pouczenie\s*:?\s*$|objaśnienia\b|instrukcj\w* wypełni\w*( \w+)?\s*:?\s*$)"
)
# Nagłówek lub stopka strony: „1/6”, „strona 1/2”, „Wersja styczeń 2026 r. | Strona 1 z 2”.
_PAGE_NUMBER = re.compile(r"(?i)^\s*(.*\|\s*)?(strona\s+)?\d{1,3}\s*(/|z|of)\s*\d{1,3}\s*$")
# W pominiętym fragmencie „nagłówek” z interpunkcją na końcu („PESEL;”) to zwykle wyraz
# pisany wielkimi literami w zdaniu, a nie początek nowej sekcji.
_SENTENCE_END = re.compile(r"[;,]\s*$")
REPEAT_MARKER = "[POWTÓRZENIE]"
MIN_REPEAT_LINES = 4
MIN_REPEAT_CHARS = 120


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

    def iter_content_blocks(self, exclude_boilerplate: bool = True) -> Iterator[tuple[int, Block]]:
        """Bloki z numerem strony, z pominięciem klauzuli RODO (gdy `exclude_boilerplate`)."""
        skipping = False
        for page in self.pages:
            for block in page.blocks:
                if exclude_boilerplate:
                    if _PAGE_NUMBER.match(block.text):
                        continue
                    if _starts_boilerplate(block):
                        skipping = True
                        continue
                    if skipping:
                        if not _ends_boilerplate(block):
                            continue
                        skipping = False
                yield page.number, block

    def to_prompt_text(
        self, exclude_boilerplate: bool = True, collapse_repeats: bool = True
    ) -> str:
        """Zwięzły tekst dokumentu z markerami `[NAGŁÓWEK]`, `[POLE]`, `[OPCJA]`, `[TABELA]`.

        `collapse_repeats`: ciąg co najmniej `MIN_REPEAT_LINES` linii identyczny
        z wcześniejszym zastępuje jedna linia `[POWTÓRZENIE]`.
        """
        by_page: dict[int, list[Block]] = {}
        for number, block in self.iter_content_blocks(exclude_boilerplate):
            by_page.setdefault(number, []).append(block)
        lines: list[str] = []
        for number, blocks in by_page.items():
            page_lines: list[str] = []
            table_rows: dict[int, list[tuple[int, str]]] | None = None
            for block in blocks:
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
                lines.append(f"=== strona {number}")
                lines.extend(page_lines)
        if collapse_repeats:
            lines = _collapse_repeats(lines)
        return "\n".join(lines)


def _starts_boilerplate(block: Block) -> bool:
    """Początek klauzuli RODO: nagłówek albo akapit „Klauzula…” lub „Zgodnie z art. 13…”."""
    if block.kind == "heading":
        return bool(_BOILERPLATE.search(block.text))
    return block.kind == "paragraph" and bool(_BOILERPLATE_PARAGRAPH.match(block.text))


def _ends_boilerplate(block: Block) -> bool:
    """Klauzulę kończy inny nagłówek albo miejsce na dane (pole formularza)."""
    if block.kind == "heading":
        return not _SENTENCE_END.search(block.text)
    return block.kind == "input_placeholder" or bool(_FILL_RUN.search(block.text))


def _is_page_header(line: str) -> bool:
    return line.startswith("=== strona ")


def _collapse_repeats(lines: list[str]) -> list[str]:
    """Zastępuje powtórzone ciągi linii znacznikiem; nagłówki stron nie przerywają ciągu."""
    content = [i for i, line in enumerate(lines) if not _is_page_header(line)]
    keys = [lines[i].casefold() for i in content]
    seen: dict[str, list[int]] = {}
    replaced: dict[int, str] = {}  # indeks w `lines` → linia zastępcza ("" = usuń)
    pos = 0
    while pos < len(keys):
        best = 0
        for start in seen.get(keys[pos], []):
            length = 0
            while (
                pos + length < len(keys)
                and start + length < pos
                and keys[start + length] == keys[pos + length]
            ):
                length += 1
            best = max(best, length)
        if (
            best >= MIN_REPEAT_LINES
            and sum(len(keys[k]) for k in range(pos, pos + best)) >= MIN_REPEAT_CHARS
        ):
            first = lines[content[pos]]
            replaced[content[pos]] = f"{REPEAT_MARKER} fragment jak wyżej, od „{first[:60]}”"
            for k in range(pos + 1, pos + best):
                replaced[content[k]] = ""
            pos += best
            continue
        seen.setdefault(keys[pos], []).append(pos)
        pos += 1
    out = [replaced.get(i, line) for i, line in enumerate(lines)]
    out = [line for line in out if line]
    # Strona, z której został tylko nagłówek „=== strona N”, nic nie wnosi.
    return [
        line
        for i, line in enumerate(out)
        if not (_is_page_header(line) and (i + 1 == len(out) or _is_page_header(out[i + 1])))
    ]


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
