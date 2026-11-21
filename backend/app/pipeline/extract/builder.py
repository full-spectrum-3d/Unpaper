"""DocumentBuilder - zbiera bloki stron i nadaje im kolejne id `b1, b2…`."""

from app.models.document import (
    BBox,
    Block,
    BlockKind,
    DocumentModel,
    ExtractionMethod,
    Page,
    SourceInfo,
    TablePos,
)


class DocumentBuilder:
    def __init__(self, method: ExtractionMethod) -> None:
        self.method: ExtractionMethod = method
        self._pages: list[list[Block]] = []
        self._next_id = 1

    def new_page(self) -> None:
        self._pages.append([])

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def add(
        self,
        kind: BlockKind,
        text: str,
        *,
        bbox: BBox | None = None,
        confidence: float | None = None,
        table: TablePos | None = None,
    ) -> None:
        if not self._pages:
            self.new_page()
        if confidence is not None:
            confidence = min(1.0, max(0.0, confidence))
        self._pages[-1].append(
            Block(
                id=f"b{self._next_id}",
                kind=kind,
                text=text,
                bbox=bbox,
                ocr_confidence=confidence,
                table=table,
            )
        )
        self._next_id += 1

    def build(self) -> DocumentModel:
        """Puste strony na końcu są usuwane; dokument zawsze ma co najmniej jedną stronę."""
        pages = list(self._pages)
        while pages and not pages[-1]:
            pages.pop()
        if not pages:
            pages = [[]]
        return DocumentModel(
            source=SourceInfo(method=self.method, pages=len(pages)),
            pages=[Page(number=i, blocks=blocks) for i, blocks in enumerate(pages, start=1)],
        )
