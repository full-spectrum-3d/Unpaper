"""Silnik układu: elementy strony z geometrią → linie → bloki (projekt ekstrakcji §4.3).

Wspólny dla PDF, OCR, pól tekstowych DOCX i XLSX. Wejście to fragmenty tekstu (`Span`),
puste ramki (`Frame` - miejsca do wypełnienia albo kratki checkboxów) i tabele
(`TableGrid`) w punktach, z osią `y` skierowaną w dół. Wynik trafia do `DocumentBuilder`
w kolejności czytania: linie z góry na dół, segmenty linii od lewej.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import median
from typing import Literal

from app.models.document import BBox, BlockKind, TablePos
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.text_rules import (
    FILL_RUN,
    is_fill_only,
    looks_like_heading,
    split_checkbox_options,
)

CHECKBOX_MIN_PT = 5.0
CHECKBOX_MAX_PT = 24.0
CHECKBOX_SQUARENESS = 0.4
"""Maksymalna różnica boków kratki względem dłuższego boku."""
CHECKBOX_TEXT_GAP_FACTOR = 3.0
"""Tekst opcji zaczyna się najdalej 3 szerokości kratki od niej."""
SEGMENT_GAP_FACTOR = 2.0
WRAP_GAP_FACTOR = 0.8
WRAP_WIDTH_RATIO = 0.85
LINE_OVERLAP_RATIO = 0.5
LINE_HEIGHT_RATIO = 3.0
"""Element ponad 3 razy wyższy od linii (np. duże pole tekstowe) tworzy własną linię."""
TALL_SHIFT_FACTOR = 1.5
"""Wysoka ramka w kolejności czytania idzie za tekstem zaczynającym się do 1,5 linii niżej."""
FRAME_TOUCH_PT = 2.0
FRAME_MIN_PT = 2.0
LABEL_MAX_CHARS = 80
BOLD_SIGNAL_MAX_SHARE = 0.5
_NEW_ITEM = re.compile(r"^(\d+[.)]|[a-zA-Z][.)]\s|[-\u2013\u2022*])")
"""Początek kolejnego punktu listy - takiej linii nie doklejamy do poprzedniej."""


@dataclass(frozen=True, slots=True)
class Span:
    text: str
    bbox: BBox
    confidence: float | None = None
    bold: bool = False
    size: float | None = None


@dataclass(frozen=True, slots=True)
class Frame:
    bbox: BBox


@dataclass(frozen=True, slots=True)
class TableGrid:
    bbox: BBox
    cells: Sequence[tuple[int, int, str]]
    """(wiersz, kolumna, tekst) - kolumny i wiersze od 0."""


ItemKind = Literal["text", "field", "check", "table"]


@dataclass(slots=True)
class _Item:
    kind: ItemKind
    bbox: BBox
    span: Span | None = None
    table: TableGrid | None = None

    @property
    def height(self) -> float:
        return self.bbox.y1 - self.bbox.y0


@dataclass(slots=True)
class _Segment:
    kind: ItemKind
    items: list[_Item] = field(default_factory=list)

    @property
    def bbox(self) -> BBox:
        return _union([item.bbox for item in self.items])

    @property
    def text(self) -> str:
        return " ".join(i.span.text.strip() for i in self.items if i.span and i.span.text.strip())

    @property
    def bold(self) -> bool:
        return all(i.span.bold for i in self.items if i.span)

    @property
    def size(self) -> float | None:
        sizes = [i.span.size for i in self.items if i.span and i.span.size]
        return max(sizes) if sizes else None

    @property
    def confidence(self) -> float | None:
        values = [i.span.confidence for i in self.items if i.span and i.span.confidence is not None]
        return sum(values) / len(values) if values else None


@dataclass(frozen=True, slots=True)
class _PageStyle:
    body_size: float | None
    bold_signal: bool
    """Pogrubienie wyróżnia nagłówki tylko wtedy, gdy większość tekstu nie jest pogrubiona."""


@dataclass(slots=True)
class _Out:
    kind: BlockKind
    text: str
    bbox: BBox
    confidence: float | None
    line: int
    alone: bool
    table: TableGrid | None = None


def layout_page(
    builder: DocumentBuilder,
    spans: Sequence[Span],
    frames: Sequence[Frame] = (),
    tables: Sequence[TableGrid] = (),
) -> None:
    """Dodaje bloki jednej strony do bieżącej strony `builder`."""
    texts = [s for s in spans if s.text.strip()]
    items = [_Item("text", s.bbox, span=s) for s in texts]
    for frame in _prepare_frames(frames, texts):
        items.append(_Item("check" if _is_checkbox(frame) else "field", frame))
    items.extend(_Item("table", t.bbox, table=t) for t in tables)

    style = _PageStyle(_body_size(texts), _bold_share(texts) < BOLD_SIGNAL_MAX_SHARE)
    outs: list[_Out] = []
    for line_no, line in enumerate(_group_lines(items)):
        outs.extend(_classify_line(line, line_no, style))
    outs = _merge_wrapped(outs, texts)
    _mark_labels(outs)
    _emit(builder, _collapse_fields(outs))


# --- ramki -------------------------------------------------------------------------------


def _prepare_frames(frames: Sequence[Frame], spans: Sequence[Span]) -> list[BBox]:
    """Odrzuca ramki zdegenerowane i ramki z tekstem w środku, scala sąsiadujące."""
    centers = [((s.bbox.x0 + s.bbox.x1) / 2, (s.bbox.y0 + s.bbox.y1) / 2) for s in spans]
    boxes = [
        f.bbox
        for f in frames
        if f.bbox.x1 - f.bbox.x0 >= FRAME_MIN_PT
        and f.bbox.y1 - f.bbox.y0 >= FRAME_MIN_PT
        and not any(_contains(f.bbox, x, y) for x, y in centers)
    ]
    boxes = _merge_runs(boxes, horizontal=True)
    return _merge_runs(boxes, horizontal=False)


def _merge_runs(boxes: list[BBox], *, horizontal: bool) -> list[BBox]:
    """Scala ramki stykające się w poziomie (ten sam pas y) albo w pionie (te same x)."""
    groups: dict[tuple[int, int], list[BBox]] = defaultdict(list)
    for box in boxes:
        key = (box.y0, box.y1) if horizontal else (box.x0, box.x1)
        groups[(round(key[0] / FRAME_TOUCH_PT), round(key[1] / FRAME_TOUCH_PT))].append(box)
    merged: list[BBox] = []
    for group in groups.values():
        group.sort(key=lambda b: b.x0 if horizontal else b.y0)
        current = group[0]
        for box in group[1:]:
            gap = box.x0 - current.x1 if horizontal else box.y0 - current.y1
            if gap <= FRAME_TOUCH_PT:
                current = _union([current, box])
            else:
                merged.append(current)
                current = box
        merged.append(current)
    return merged


def _is_checkbox(box: BBox) -> bool:
    w, h = box.x1 - box.x0, box.y1 - box.y0
    in_range = all(CHECKBOX_MIN_PT <= v <= CHECKBOX_MAX_PT for v in (w, h))
    return in_range and abs(w - h) <= CHECKBOX_SQUARENESS * max(w, h)


# --- linie i segmenty --------------------------------------------------------------------


def _group_lines(items: list[_Item]) -> list[list[_Item]]:
    # Wysoka ramka zaczynająca się tuż nad etykietą ma iść po niej, nie przed nią.
    text_heights = [i.height for i in items if i.kind == "text"]
    typical = median(text_heights) if text_heights else 0.0

    def key(item: _Item) -> tuple[float, float]:
        tall = item.kind != "text" and item.height > LINE_HEIGHT_RATIO * typical
        return (item.bbox.y0 + (TALL_SHIFT_FACTOR * typical if tall else 0.0), item.bbox.x0)

    items = sorted(items, key=key)
    lines: list[list[_Item]] = []
    anchor: _Item | None = None
    for item in items:
        if anchor is not None and item.kind != "table" and _same_line(anchor, item):
            lines[-1].append(item)
            continue
        lines.append([item])
        anchor = None if item.kind == "table" else item
    for line in lines:
        line.sort(key=lambda i: i.bbox.x0)
    return lines


def _same_line(anchor: _Item, item: _Item) -> bool:
    low, high = sorted((anchor.height, item.height))
    if low <= 0 or high > low * LINE_HEIGHT_RATIO:
        return False
    overlap = min(anchor.bbox.y1, item.bbox.y1) - max(anchor.bbox.y0, item.bbox.y0)
    return overlap >= LINE_OVERLAP_RATIO * low


def _segments(line: list[_Item]) -> list[_Segment]:
    height = median(i.height for i in line)
    segments: list[_Segment] = []
    for item in line:
        last = segments[-1] if segments else None
        if (
            last is not None
            and item.kind == "text"
            and last.kind == "text"
            and item.bbox.x0 - last.items[-1].bbox.x1 <= SEGMENT_GAP_FACTOR * height
        ):
            last.items.append(item)
        else:
            segments.append(_Segment(item.kind, [item]))
    return segments


# --- klasyfikacja ------------------------------------------------------------------------


def _classify_line(line: list[_Item], line_no: int, style: _PageStyle) -> list[_Out]:
    segments = _segments(line)
    option_of = _pair_checkboxes(segments)
    alone = len(segments) == 1
    outs: list[_Out] = []
    for index, seg in enumerate(segments):
        bbox = seg.bbox
        match seg.kind:
            case "table":
                assert seg.items[0].table is not None  # noqa: S101 - zapewnia _Item
                outs.append(_Out("table", "", bbox, None, line_no, alone, seg.items[0].table))
            case "field":
                outs.append(_Out("input_placeholder", "", bbox, None, line_no, alone))
            case "check":
                if index not in option_of.values():
                    outs.append(_Out("input_placeholder", "", bbox, None, line_no, alone))
            case "text":
                outs.extend(_classify_text(seg, index in option_of, line_no, alone, style))
    return outs


def _pair_checkboxes(segments: list[_Segment]) -> dict[int, int]:
    """Indeks segmentu tekstu → indeks kratki, której jest opisem.

    Opis stoi za kratką. Kratka bez opisu (np. „Nr lokalu □ Kod …”) jest polem.
    """
    pairs: dict[int, int] = {}
    for index, seg in enumerate(segments):
        if seg.kind != "check":
            continue
        width = seg.bbox.x1 - seg.bbox.x0
        max_gap = CHECKBOX_TEXT_GAP_FACTOR * width
        after = index + 1
        if after < len(segments) and segments[after].kind == "text" and after not in pairs:
            followed_by_field = after + 1 < len(segments) and segments[after + 1].kind == "field"
            if segments[after].bbox.x0 - seg.bbox.x1 <= max_gap and not followed_by_field:
                pairs[after] = index
    return pairs


def _classify_text(
    seg: _Segment, is_option: bool, line_no: int, alone: bool, style: _PageStyle
) -> list[_Out]:
    text, bbox, conf = seg.text, seg.bbox, seg.confidence
    options = split_checkbox_options(text)
    if options is not None:
        return [_Out("checkbox_option", o, bbox, conf, line_no, alone) for o in options]
    if is_option:
        return [_Out("checkbox_option", text, bbox, conf, line_no, alone)]
    if is_fill_only(text):
        return [_Out("input_placeholder", "", bbox, conf, line_no, alone)]
    heading = looks_like_heading(
        text,
        bold=seg.bold and style.bold_signal,
        size=seg.size,
        body_size=style.body_size,
        alone=alone,
    )
    return [_Out("heading" if heading else "paragraph", text, bbox, conf, line_no, alone)]


def _merge_wrapped(outs: list[_Out], spans: Sequence[Span]) -> list[_Out]:
    """Skleja zawinięte linie jednego akapitu (projekt §4.3 pkt 5)."""
    if not spans:
        return outs
    left = min(s.bbox.x0 for s in spans)
    right = max(s.bbox.x1 for s in spans)
    threshold = left + WRAP_WIDTH_RATIO * (right - left)
    merged: list[_Out] = []
    for out in outs:
        prev = merged[-1] if merged else None
        if (
            prev is not None
            and prev.kind == out.kind == "paragraph"
            and prev.alone
            and out.alone
            and out.line == prev.line + 1
            and prev.bbox.x1 >= threshold
            and out.bbox.y0 - prev.bbox.y1 < WRAP_GAP_FACTOR * (prev.bbox.y1 - prev.bbox.y0)
            and not FILL_RUN.search(prev.text)
            and not FILL_RUN.search(out.text)
            and not prev.text.rstrip().endswith(":")
            and not _NEW_ITEM.match(out.text)
            and not (prev.text.rstrip().endswith(".") and out.text[:1].isupper())
        ):
            confs = [c for c in (prev.confidence, out.confidence) if c is not None]
            merged[-1] = _Out(
                "paragraph",
                f"{prev.text} {out.text}",
                _union([prev.bbox, out.bbox]),
                sum(confs) / len(confs) if confs else None,
                out.line,
                True,
            )
            continue
        merged.append(out)
    return merged


def _collapse_fields(outs: list[_Out]) -> list[_Out]:
    """Kolejne pola bez tekstu między nimi → jedno pole.

    Siatki komórek (arkusze, deklaracje) dają ciągi pustych ramek bez etykiet; dla LLM to
    jedno miejsce do wypełnienia, a nie kilkanaście znaczników `[POLE]` z rzędu.
    """
    collapsed: list[_Out] = []
    for out in outs:
        prev = collapsed[-1] if collapsed else None
        if prev is not None and prev.kind == out.kind == "input_placeholder":
            prev.bbox = _union([prev.bbox, out.bbox])
            continue
        collapsed.append(out)
    return collapsed


def _mark_labels(outs: list[_Out]) -> None:
    """Tekst tuż przed polem (ta sama linia albo krótki blok) albo kończący się `:` → label."""
    for index, out in enumerate(outs):
        if out.kind != "paragraph" or len(out.text) > LABEL_MAX_CHARS:
            continue
        nxt = outs[index + 1] if index + 1 < len(outs) else None
        before_field = nxt is not None and nxt.kind == "input_placeholder"
        if before_field or out.text.rstrip().endswith(":"):
            out.kind = "label"


def _emit(builder: DocumentBuilder, outs: list[_Out]) -> None:
    for out in outs:
        builder.add(out.kind, out.text, bbox=out.bbox, confidence=out.confidence)
        if out.table is None:
            continue
        for row, col, text in sorted(out.table.cells, key=lambda c: (c[0], c[1])):
            builder.add("table_cell", " ".join(text.split()), table=TablePos(row=row, col=col))


# --- geometria ---------------------------------------------------------------------------


def _union(boxes: Sequence[BBox]) -> BBox:
    return BBox(
        x0=min(b.x0 for b in boxes),
        y0=min(b.y0 for b in boxes),
        x1=max(b.x1 for b in boxes),
        y1=max(b.y1 for b in boxes),
    )


def _contains(box: BBox, x: float, y: float) -> bool:
    return box.x0 <= x <= box.x1 and box.y0 <= y <= box.y1


def _bold_share(spans: Sequence[Span]) -> float:
    total = sum(len(s.text) for s in spans)
    return sum(len(s.text) for s in spans if s.bold) / total if total else 0.0


def _body_size(spans: Sequence[Span]) -> float | None:
    """Mediana rozmiaru czcionki ważona liczbą znaków."""
    weighted = sorted((s.size, len(s.text)) for s in spans if s.size)
    total = sum(w for _, w in weighted)
    if not total:
        return None
    acc = 0
    for size, weight in weighted:
        acc += weight
        if acc * 2 >= total:
            return size
    return weighted[-1][0]
