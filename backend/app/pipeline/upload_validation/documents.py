"""PDF i obrazy: złożoność i czytelność (spec §6.3 pkt 8 i 9).

- PDF: otwarcie w PDFium, liczba stron ≤ `max_pdf_pages`, załadowanie pierwszej strony.
  Plik zabezpieczony hasłem użytkownika odrzucamy. Plik z samym hasłem właściciela otwiera
  się bez hasła, więc go przyjmujemy.
- JPEG/PNG: wymiary odczytujemy z nagłówka przed dekodowaniem, potem `verify()`. JPEG
  dodatkowo dekodujemy w skali 1/8 (`draft`), co tanio wykrywa ucięte pliki. Pillow
  dostaje tylko dekoder oczekiwanego formatu.
"""

import warnings
from typing import IO

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image, UnidentifiedImageError

from app.pipeline.pdfium_lock import PDFIUM_LOCK
from app.pipeline.upload_validation.errors import UploadError, UploadErrorCode
from app.pipeline.upload_validation.policy import FileKind, UploadLimits

_PDF_PROTECTED_ERRORS = frozenset({pdfium_c.FPDF_ERR_PASSWORD, pdfium_c.FPDF_ERR_SECURITY})
_PIL_FORMAT: dict[FileKind, str] = {FileKind.JPEG: "JPEG", FileKind.PNG: "PNG"}
_JPEG_DRAFT_SCALE = 8


def inspect_pdf(file: IO[bytes], limits: UploadLimits) -> int:
    """Zwraca liczbę stron."""
    file.seek(0)
    try:
        with PDFIUM_LOCK:
            try:
                document = pdfium.PdfDocument(file)
            except pdfium.PdfiumError as exc:
                if exc.err_code in _PDF_PROTECTED_ERRORS:
                    raise UploadError(
                        UploadErrorCode.DOCUMENT_UNREADABLE,
                        "Dokument PDF jest zabezpieczony hasłem",
                    ) from exc
                raise UploadError(
                    UploadErrorCode.DOCUMENT_UNREADABLE, "Plik PDF jest uszkodzony"
                ) from exc
            try:
                pages = len(document)
                if pages > limits.max_pdf_pages:
                    raise UploadError(
                        UploadErrorCode.DOCUMENT_TOO_COMPLEX,
                        f"Liczba stron: {pages}, dopuszczalna: {limits.max_pdf_pages}",
                    )
                try:
                    document[0].close()
                except pdfium.PdfiumError as exc:
                    raise UploadError(
                        UploadErrorCode.DOCUMENT_UNREADABLE, "Nie można odczytać strony PDF"
                    ) from exc
            finally:
                document.close()
    finally:
        file.seek(0)
    return pages


def inspect_image(file: IO[bytes], kind: FileKind, limits: UploadLimits) -> tuple[int, int]:
    """Zwraca (szerokość, wysokość)."""
    image_format = _PIL_FORMAT[kind]
    file.seek(0)
    try:
        with warnings.catch_warnings():
            # Limit pikseli egzekwujemy sami (MAX_IMAGE_PIXELS); ostrzeżenie Pillow jest zbędne.
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            width, height = _read_dimensions(file, image_format)
            if width * height > limits.max_image_pixels:
                raise UploadError(
                    UploadErrorCode.DOCUMENT_TOO_COMPLEX,
                    f"Obraz ma {width}x{height} = {width * height} pikseli, "
                    f"dopuszczalne jest {limits.max_image_pixels}",
                )
            _verify_image(file, image_format, width, height)
    finally:
        file.seek(0)
    return width, height


def _read_dimensions(file: IO[bytes], image_format: str) -> tuple[int, int]:
    try:
        with Image.open(file, formats=[image_format]) as image:
            width, height = image.size
    except Image.DecompressionBombError as exc:
        raise UploadError(
            UploadErrorCode.DOCUMENT_TOO_COMPLEX, "Obraz ma zbyt dużą liczbę pikseli"
        ) from exc
    except UnidentifiedImageError as exc:
        raise UploadError(
            UploadErrorCode.DOCUMENT_UNREADABLE, f"Nie można odczytać obrazu {image_format}"
        ) from exc
    except Exception as exc:  # dekodery Pillow rzucają różne wyjątki dla uszkodzonych plików
        raise UploadError(
            UploadErrorCode.DOCUMENT_UNREADABLE, f"Obraz {image_format} jest uszkodzony"
        ) from exc
    if width < 1 or height < 1:
        raise UploadError(UploadErrorCode.DOCUMENT_UNREADABLE, "Obraz ma zerowy wymiar")
    return width, height


def _verify_image(file: IO[bytes], image_format: str, width: int, height: int) -> None:
    try:
        file.seek(0)
        with Image.open(file, formats=[image_format]) as image:
            image.verify()
        if image_format == "JPEG":
            file.seek(0)
            with Image.open(file, formats=[image_format]) as image:
                image.draft(
                    "L", (max(1, width // _JPEG_DRAFT_SCALE), max(1, height // _JPEG_DRAFT_SCALE))
                )
                image.load()
    except Exception as exc:  # j.w.
        raise UploadError(
            UploadErrorCode.DOCUMENT_UNREADABLE, f"Obraz {image_format} jest uszkodzony"
        ) from exc
