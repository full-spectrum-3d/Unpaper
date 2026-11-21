"""OCR na prawdziwym Tesseracie (znacznik `ocr`, domyślnie pomijany)."""

import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.pipeline.extract.image import TesseractOcr

pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(shutil.which("tesseract") is None, reason="brak tesseract"),
]


def test_tesseract_reads_polish_text() -> None:
    image = Image.new("L", (1200, 200), 255)
    draw = ImageDraw.Draw(image)
    draw.text((40, 60), "Wniosek o zwrot opłaty", fill=0, font=ImageFont.load_default(48))
    words = TesseractOcr("pol").recognize(image)
    text = " ".join(w.text for w in words)
    assert "Wniosek" in text
    assert all(0 <= w.confidence <= 1 for w in words)
