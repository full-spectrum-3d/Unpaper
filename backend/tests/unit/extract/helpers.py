"""Pomocniki do testów ekstrakcji."""

from app.models.document import BBox, DocumentModel
from app.pipeline.extract.builder import DocumentBuilder
from app.pipeline.extract.layout import Frame, Span, TableGrid, layout_page


def box(x0: float, y0: float, x1: float, y1: float) -> BBox:
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


def span(
    text: str,
    x0: float,
    top: float,
    x1: float | None = None,
    h: float = 10,
    **kw: object,
) -> Span:
    width = x1 - x0 if x1 is not None else len(text) * 5
    return Span(text, box(x0, top, x0 + width, top + h), **kw)  # type: ignore[arg-type]


def frame(x0: float, y0: float, x1: float, y1: float) -> Frame:
    return Frame(box(x0, y0, x1, y1))


def run_layout(
    spans: list[Span], frames: list[Frame] | None = None, tables: list[TableGrid] | None = None
) -> DocumentModel:
    builder = DocumentBuilder("pdf_text")
    builder.new_page()
    layout_page(builder, spans, frames or [], tables or [])
    return builder.build()


def kinds(doc: DocumentModel) -> list[tuple[str, str]]:
    return [(b.kind, b.text) for b in doc.iter_blocks()]
