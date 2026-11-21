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
        self._sizes: list[tuple[float, float] | None] = []
        self._next_id = 1

    def new_page(self, size: tuple[float, float] | None = None) -> None:
        """`size` to (szerokość, wysokość) strony w jednostkach `bbox`, jeśli format je zna."""
        self._pages.append([])
        self._sizes.append(size if size and size[0] > 0 and size[1] > 0 else None)

    def rotate_page(self) -> None:
        """Bieżąca strona obrócona o 90°: zamiana szerokości z wysokością."""
        size = self._sizes[-1]
        if size is not None:
            self._sizes[-1] = (size[1], size[0])

    def ensure_new_page(self) -> None:
        """Nowa strona, chyba że bieżąca jest jeszcze pusta (dwa podziały z rzędu)."""
        if not self._pages or self._pages[-1]:
            self.new_page()

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
        sizes = [*self._sizes, None][: len(pages)]
        return DocumentModel(
            source=SourceInfo(method=self.method, pages=len(pages)),
            pages=[
                Page(
                    number=i,
                    blocks=blocks,
                    width=size[0] if size else None,
                    height=size[1] if size else None,
                )
                for i, (blocks, size) in enumerate(zip(pages, sizes, strict=True), start=1)
            ],
        )
