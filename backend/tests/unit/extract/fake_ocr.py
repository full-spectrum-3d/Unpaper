"""Atrapa silnika OCR: zwraca zadane słowa (współrzędne w pikselach) dla każdej strony."""

from PIL import Image

from app.pipeline.extract.image import OcrUnavailableError, OcrWord


class FakeOcr:
    def __init__(
        self, pages: list[list[OcrWord]] | None = None, *, fail: bool = False, rotate: int = 0
    ) -> None:
        self.pages = list(pages or [])
        self.fail = fail
        self.rotate = rotate
        self.sizes: list[tuple[int, int]] = []
        self.images: list[Image.Image] = []
        self.orient_calls = 0
        self.workers = 1

    def orient(self, image: Image.Image) -> Image.Image:
        self.orient_calls += 1
        return image.rotate(self.rotate, expand=True) if self.rotate else image

    def recognize(self, image: Image.Image) -> list[OcrWord]:
        self.sizes.append(image.size)
        self.images.append(image)
        if self.fail:
            raise OcrUnavailableError("brak tesseracta")
        return self.pages.pop(0) if self.pages else []


def word(
    text: str, left: int, top: int, width: int = 60, height: int = 20, conf: float = 0.9
) -> OcrWord:
    return OcrWord(text, left, top, width, height, conf, line_height=height)
