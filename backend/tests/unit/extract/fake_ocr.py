"""Atrapa silnika OCR: zwraca zadane słowa (współrzędne w pikselach) dla każdej strony."""

from PIL import Image

from app.pipeline.extract.image import OcrUnavailableError, OcrWord


class FakeOcr:
    def __init__(self, pages: list[list[OcrWord]] | None = None, *, fail: bool = False) -> None:
        self.pages = list(pages or [])
        self.fail = fail
        self.sizes: list[tuple[int, int]] = []

    def recognize(self, image: Image.Image) -> list[OcrWord]:
        self.sizes.append(image.size)
        if self.fail:
            raise OcrUnavailableError("brak tesseracta")
        return self.pages.pop(0) if self.pages else []


def word(
    text: str, left: int, top: int, width: int = 60, height: int = 20, conf: float = 0.9
) -> OcrWord:
    return OcrWord(text, left, top, width, height, conf, line_height=height)
