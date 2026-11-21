"""DOCX: python-docx - akapity, nagłówki, listy, tabele, pola formularza, pola tekstowe.

Elementy `w:body` czytamy po kolei (także zawartość `w:sdt`). Pola tekstowe z pozycją
absolutną (dokumenty przekonwertowane z PDF mają w nich całą treść) przechodzą przez silnik
układu. Każde pole tekstowe jest w pliku dwa razy: `mc:Choice` (DrawingML) i `mc:Fallback`
(VML) - czytamy tylko pierwsze.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO

import docx
from docx.document import Document
from lxml import etree

from app.models.document import BBox, DocumentModel, TablePos
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.grid import cells_from_segments
from app.pipeline.extract.layout import Frame, Span, layout_page
from app.pipeline.extract.text_rules import (
    CHECKBOX_GLYPHS,
    HEADING_MAX_CHARS,
    is_fill_only,
    is_heading_style,
    looks_like_heading,
    split_checkbox_options,
)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
_V = "urn:schemas-microsoft-com:vml"


def _w(tag: str) -> str:
    return f"{{{_W}}}{tag}"


EMU_PER_PT = 12700
FILL_MARKER = "……"
"""Wstawiany w miejsce pola FORMTEXT - `DocumentModel` zamieni go na `[POLE]`."""
CHECKBOX_MARKER = "☐"
LABEL_MAX_CHARS = 80
TEXTBOX_LINE_PT = 12.0
MIN_LINE_PT = 0.25
"""Puste pola tekstowe szerokości 0,1 pt (artefakt konwersji z PDF) to nie linie ramek."""

_PAGE_BREAK = object()
_SEGMENT_BREAK = object()
_SEGMENT_SPACES = re.compile(r" {4,}")
_SKIP_SUBTREES = frozenset(
    {
        f"{{{_MC}}}Fallback",
        _w("txbxContent"),
        _w("drawing"),
        _w("pict"),
        _w("del"),
        _w("delText"),
        _w("instrText"),
        _w("rPr"),
        _w("pPr"),
        _w("sdtPr"),
    }
)
_VML_LENGTH = re.compile(
    r"(?P<key>margin-left|margin-top|left|top|width|height)\s*:\s*"
    r"(?P<value>-?[\d.]+)(?P<unit>pt|in|cm|mm|px)?"
)
_VML_UNIT_PT = {"pt": 1.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "px": 0.75, None: 0.75}

Piece = str | object


@dataclass(slots=True)
class _Run:
    """Tekst akapitu z podziałami (strona, segment) i cechami pisma."""

    pieces: list[Piece] = field(default_factory=list)
    bold: list[bool] = field(default_factory=list)
    sizes: list[float] = field(default_factory=list)


def extract_docx(file: IO[bytes]) -> DocumentModel:
    document = docx.Document(file)
    builder = DocumentBuilder("docx")
    builder.new_page()
    _Walker(document, builder).body(document.element.body)
    return builder.build()


class _Walker:
    def __init__(self, document: Document, builder: DocumentBuilder) -> None:
        self.builder = builder
        self.bullets = _checkbox_bullets(document)
        self.heading_styles = {
            s.style_id
            for s in document.styles
            if is_heading_style(getattr(s, "name", None)) and s.style_id
        }

    # --- struktura ---------------------------------------------------------------------

    def body(self, container: etree._Element) -> None:
        for child in container:
            if child.tag == _w("p"):
                self.paragraph(child)
            elif child.tag == _w("tbl"):
                self.table(child)
            elif child.tag == _w("sdt"):
                content = child.find(_w("sdtContent"))
                if content is not None:
                    self.body(content)

    def paragraph(self, p: etree._Element) -> None:
        ppr = p.find(_w("pPr"))
        if ppr is not None and _on(ppr.find(_w("pageBreakBefore"))):
            self.builder.ensure_new_page()
        run = _Run()
        _collect(p, run)
        checkbox_bullet = self._is_checkbox_bullet(ppr)
        heading_style = self._is_heading_style(ppr)
        bold = bool(run.bold) and all(run.bold)
        size = max(run.sizes) if run.sizes else None
        for piece in _split_pages(run.pieces):
            if piece is _PAGE_BREAK:
                self.builder.ensure_new_page()
                continue
            assert isinstance(piece, list)  # noqa: S101 - _split_pages zwraca listy segmentów
            alone = len(piece) == 1
            for text in piece:
                self._emit_text(text, checkbox_bullet, heading_style, bold, size, alone)
                checkbox_bullet = False
        self.textboxes(p)
        if ppr is not None:
            sect = ppr.find(_w("sectPr"))
            if sect is not None and _section_type(sect) != "continuous":
                self.builder.ensure_new_page()

    def table(self, tbl: etree._Element) -> None:
        cells: list[tuple[int, int, etree._Element]] = []
        columns = 0
        for row_index, tr in enumerate(tbl.findall(_w("tr"))):
            col = 0
            for tc in tr.findall(_w("tc")):
                tcpr = tc.find(_w("tcPr"))
                span = _val_int(tcpr, "gridSpan", 1)
                vmerge = tcpr.find(_w("vMerge")) if tcpr is not None else None
                if vmerge is None or vmerge.get(_w("val")) == "restart":
                    cells.append((row_index, col, tc))
                col += span
            columns = max(columns, col)
        if columns <= 1:
            # Tabela z jedną kolumną to tylko ramki wokół akapitów.
            for _, _, tc in cells:
                self.body(tc)
            return
        self.builder.add("table", "")
        for row, col, tc in cells:
            text = " ".join(_cell_text(tc).split())
            self.builder.add("table_cell", text, table=TablePos(row=row, col=col))

    def textboxes(self, p: etree._Element) -> None:
        spans: list[Span] = []
        outlines: list[BBox] = []
        for shape in _shapes(p):
            if shape.paragraphs:
                line = shape.height / len(shape.paragraphs)
                line = min(line, TEXTBOX_LINE_PT) if line > 0 else TEXTBOX_LINE_PT
                for index, (text, bold, size) in enumerate(shape.paragraphs):
                    top = shape.y + index * line
                    spans.append(
                        Span(text, _bbox(shape.x, top, shape.width, line), bold=bold, size=size)
                    )
            elif not shape.is_picture and min(shape.width, shape.height) >= MIN_LINE_PT:
                outlines.append(_bbox(shape.x, shape.y, shape.width, shape.height))
        if spans:
            frames = [Frame(cell) for cell in cells_from_segments(outlines)]
            layout_page(self.builder, spans, frames)

    # --- klasyfikacja ------------------------------------------------------------------

    def _emit_text(
        self,
        text: str,
        checkbox_bullet: bool,
        heading_style: bool,
        bold: bool,
        size: float | None,
        alone: bool,
    ) -> None:
        text = " ".join(text.split())
        if not text:
            return
        options = split_checkbox_options(text)
        if options is not None:
            for option in options:
                self.builder.add("checkbox_option", option)
        elif checkbox_bullet:
            self.builder.add("checkbox_option", text)
        elif is_fill_only(text):
            self.builder.add("input_placeholder", "")
        elif (heading_style and len(text) <= HEADING_MAX_CHARS) or looks_like_heading(
            text, bold=bold, size=size, body_size=None, alone=alone
        ):
            self.builder.add("heading", text)
        elif text.endswith(":") and len(text) <= LABEL_MAX_CHARS:
            self.builder.add("label", text)
        else:
            self.builder.add("paragraph", text)

    def _is_checkbox_bullet(self, ppr: etree._Element | None) -> bool:
        if ppr is None:
            return False
        num = ppr.find(_w("numPr"))
        if num is None:
            return False
        num_id = num.find(_w("numId"))
        level = num.find(_w("ilvl"))
        key = (
            num_id.get(_w("val")) if num_id is not None else None,
            level.get(_w("val")) if level is not None else "0",
        )
        return key in self.bullets

    def _is_heading_style(self, ppr: etree._Element | None) -> bool:
        if ppr is None:
            return False
        if ppr.find(_w("outlineLvl")) is not None:
            return True
        style = ppr.find(_w("pStyle"))
        return style is not None and style.get(_w("val")) in self.heading_styles


# --- tekst akapitu -----------------------------------------------------------------------


def _collect(element: etree._Element, run: _Run) -> None:
    """Przechodzi akapit w kolejności dokumentu, pomijając pola tekstowe i usunięcia."""
    for child in element:
        tag = child.tag
        if not isinstance(tag, str) or tag in _SKIP_SUBTREES:
            continue
        if tag == _w("r"):
            _collect_run(child, run)
        elif tag == _w("sdt"):
            props = child.find(_w("sdtPr"))
            if props is not None and props.find(f"{{{_W14}}}checkbox") is not None:
                run.pieces.append(CHECKBOX_MARKER + " ")
            content = child.find(_w("sdtContent"))
            if content is not None:
                _collect(content, run)
        else:
            _collect(child, run)


def _collect_run(r: etree._Element, run: _Run) -> None:
    rpr = r.find(_w("rPr"))
    has_text = False
    for child in r:
        tag = child.tag
        if not isinstance(tag, str) or tag in _SKIP_SUBTREES:
            continue
        if tag == _w("t"):
            run.pieces.append(child.text or "")
            has_text = has_text or bool((child.text or "").strip())
        elif tag == _w("tab"):
            run.pieces.append(_SEGMENT_BREAK)
        elif tag == _w("br"):
            run.pieces.append(_PAGE_BREAK if child.get(_w("type")) == "page" else _SEGMENT_BREAK)
        elif tag == _w("cr"):
            run.pieces.append(_SEGMENT_BREAK)
        elif tag == _w("sym"):
            code = child.get(_w("char")) or ""
            if re.fullmatch(r"[0-9A-Fa-f]{2,4}", code):
                char = chr(int(code, 16))
                if char in CHECKBOX_GLYPHS or 0xF000 <= ord(char) <= 0xF0FF:
                    char = CHECKBOX_MARKER if char in CHECKBOX_GLYPHS else ""
                run.pieces.append(char + " ")
        elif tag == _w("fldChar"):
            ff = child.find(_w("ffData"))
            if ff is not None:
                if ff.find(_w("checkBox")) is not None:
                    run.pieces.append(CHECKBOX_MARKER + " ")
                elif ff.find(_w("textInput")) is not None:
                    run.pieces.append(FILL_MARKER)
    if has_text:
        run.bold.append(_on(rpr.find(_w("b"))) if rpr is not None else False)
        size = _val_int(rpr, "sz", 0)
        if size:
            run.sizes.append(size / 2)


def _split_pages(pieces: list[Piece]) -> list[object]:
    """Lista segmentów (list[str]) przedzielona znacznikami `_PAGE_BREAK`."""
    out: list[object] = []
    segments: list[str] = []
    current: list[str] = []

    def close_segment() -> None:
        text = "".join(current)
        current.clear()
        segments.extend(part for part in _SEGMENT_SPACES.split(text) if part.strip())

    for piece in pieces:
        if piece is _PAGE_BREAK:
            close_segment()
            if segments:
                out.append(list(segments))
                segments.clear()
            out.append(_PAGE_BREAK)
        elif piece is _SEGMENT_BREAK:
            close_segment()
        else:
            assert isinstance(piece, str)  # noqa: S101
            current.append(piece)
    close_segment()
    if segments:
        out.append(segments)
    return out


def _cell_text(tc: etree._Element) -> str:
    parts: list[str] = []
    for p in tc.iter(_w("p")):
        if _inside_textbox(p, tc):
            continue
        run = _Run()
        _collect(p, run)
        parts.extend(str(x) for x in run.pieces if isinstance(x, str))
        parts.append(" ")
    return "".join(parts)


def _inside_textbox(element: etree._Element, stop: etree._Element) -> bool:
    parent = element.getparent()
    while parent is not None and parent is not stop:
        if parent.tag in (_w("txbxContent"), f"{{{_MC}}}Fallback"):
            return True
        parent = parent.getparent()
    return False


# --- pola tekstowe i kształty ------------------------------------------------------------


@dataclass(slots=True)
class _Shape:
    x: float
    y: float
    width: float
    height: float
    paragraphs: list[tuple[str, bool, float | None]]
    is_picture: bool


def _shapes(p: etree._Element) -> Iterator[_Shape]:
    """Kształty zakotwiczone w akapicie: DrawingML (bez `mc:Fallback`) i VML."""
    for anchor in p.iter(f"{{{_WP}}}anchor", f"{{{_WP}}}inline"):
        if _inside_textbox(anchor, p):
            continue
        x = _offset(anchor.find(f"{{{_WP}}}positionH"))
        y = _offset(anchor.find(f"{{{_WP}}}positionV"))
        extent = anchor.find(f"{{{_WP}}}extent")
        width = _attr_int(extent, "cx") / EMU_PER_PT
        height = _attr_int(extent, "cy") / EMU_PER_PT
        picture = anchor.find(f".//{{{_A}}}blip") is not None
        yield _Shape(x, y, width, height, _textbox_paragraphs(anchor), picture)
    for pict in p.iter(_w("pict")):
        if _inside_textbox(pict, p):
            continue
        for shape in pict.iter(f"{{{_V}}}shape", f"{{{_V}}}rect"):
            dims = _vml_style(shape.get("style") or "")
            yield _Shape(
                dims.get("margin-left", dims.get("left", 0.0)),
                dims.get("margin-top", dims.get("top", 0.0)),
                dims.get("width", 0.0),
                dims.get("height", 0.0),
                _textbox_paragraphs(shape),
                shape.find(f"{{{_V}}}imagedata") is not None,
            )


def _textbox_paragraphs(shape: etree._Element) -> list[tuple[str, bool, float | None]]:
    out: list[tuple[str, bool, float | None]] = []
    for content in shape.iter(_w("txbxContent")):
        for p in content.iter(_w("p")):
            run = _Run()
            _collect(p, run)
            text = " ".join("".join(x for x in run.pieces if isinstance(x, str)).split())
            if text:
                bold = bool(run.bold) and all(run.bold)
                out.append((text, bold, max(run.sizes) if run.sizes else None))
    return out


def _offset(position: etree._Element | None) -> float:
    if position is None:
        return 0.0
    offset = position.find(f"{{{_WP}}}posOffset")
    try:
        return int(offset.text or 0) / EMU_PER_PT if offset is not None else 0.0
    except ValueError:
        return 0.0


def _vml_style(style: str) -> dict[str, float]:
    dims: dict[str, float] = {}
    for match in _VML_LENGTH.finditer(style):
        dims[match["key"]] = float(match["value"]) * _VML_UNIT_PT[match["unit"]]
    return dims


def _bbox(x: float, y: float, width: float, height: float) -> BBox:
    return BBox(x0=x, y0=y, x1=x + max(width, 0.0), y1=y + max(height, 0.0))


# --- numeracja i atrybuty ----------------------------------------------------------------


def _checkbox_bullets(document: Document) -> set[tuple[str | None, str | None]]:
    """(numId, ilvl) list, których punktorem jest glif checkboxa."""
    try:
        numbering = document.part.numbering_part.element
    except KeyError, NotImplementedError:
        return set()
    abstract: dict[str | None, set[str | None]] = {}
    for definition in numbering.iter(_w("abstractNum")):
        levels: set[str | None] = set()
        for level in definition.iter(_w("lvl")):
            text = level.find(_w("lvlText"))
            value = text.get(_w("val")) if text is not None else None
            if value and value.strip() and all(ch in CHECKBOX_GLYPHS for ch in value.strip()):
                levels.add(level.get(_w("ilvl")))
        abstract[definition.get(_w("abstractNumId"))] = levels
    bullets: set[tuple[str | None, str | None]] = set()
    for num in numbering.iter(_w("num")):
        ref = num.find(_w("abstractNumId"))
        levels = abstract.get(ref.get(_w("val")) if ref is not None else None, set())
        bullets.update((num.get(_w("numId")), level) for level in levels)
    return bullets


def _on(element: etree._Element | None) -> bool:
    """Właściwość przełącznikowa (`<w:b/>`, `<w:b w:val="0"/>`)."""
    if element is None:
        return False
    return element.get(_w("val")) not in ("0", "false", "off")


def _attr_int(element: etree._Element | None, name: str, default: int = 0) -> int:
    value = element.get(name) if element is not None else None
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _val_int(parent: etree._Element | None, tag: str, default: int) -> int:
    """Liczba z `w:val` elementu-dziecka `tag` (np. `w:sz`, `w:gridSpan`)."""
    child = parent.find(_w(tag)) if parent is not None else None
    return _attr_int(child, _w("val"), default)


def _section_type(sect: etree._Element) -> str:
    kind = sect.find(_w("type"))
    return (kind.get(_w("val")) if kind is not None else None) or "nextPage"
