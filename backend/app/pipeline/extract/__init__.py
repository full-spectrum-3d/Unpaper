"""[3] Ekstrakcja do wspólnego DocumentModel (spec §5.3, projekt ekstrakcji).

`extract()` jest synchroniczna (CPU, pdfminer, Tesseract) - wywołujący uruchamia ją
w wątku, jak `normalize`. Nie przerywa żądania z powodu OCR: strona, której nie dało się
rozpoznać, zostaje pusta z ostrzeżeniem `W11_OCR_UNAVAILABLE`.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.document import DocumentModel
from app.models.warning import ConversionWarning
from app.pipeline.extract.docx import extract_docx
from app.pipeline.extract.image import (
    OcrEngine,
    OcrStats,
    OcrUnavailableError,
    TesseractOcr,
    extract_image,
)
from app.pipeline.extract.pdf import extract_pdf
from app.pipeline.extract.xlsx import extract_xlsx
from app.pipeline.normalize import NormalizedDocument
from app.pipeline.upload_validation.policy import FileKind

logger = logging.getLogger(__name__)

LOW_OCR_CONFIDENCE = 0.6

__all__ = ["ExtractionResult", "OcrEngine", "OcrUnavailableError", "extract"]


@dataclass(slots=True)
class ExtractionResult:
    document: DocumentModel
    warnings: list[ConversionWarning] = field(default_factory=list)


def extract(
    doc: NormalizedDocument,
    settings: Settings,
    *,
    ocr: OcrEngine | None = None,
    deadline: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> ExtractionResult:
    """PDF / DOCX / XLSX / JPEG / PNG → `DocumentModel` + ostrzeżenia OCR."""
    started = clock()
    engine = (
        ocr if ocr is not None else TesseractOcr(settings.ocr_lang, deadline=deadline, clock=clock)
    )

    def check() -> None:
        if deadline is not None and clock() > deadline:
            raise AppError(ErrorCode.PROCESSING_TIMEOUT, "Przekroczono czas ekstrakcji dokumentu")

    stats = OcrStats()
    doc.file.seek(0)
    try:
        match doc.kind:
            case FileKind.PDF:
                document, stats = extract_pdf(
                    doc.file,
                    engine,
                    dpi=settings.ocr_dpi,
                    max_pixels=settings.max_image_pixels,
                    check=check,
                )
            case FileKind.DOCX:
                document = extract_docx(doc.file)
            case FileKind.XLSX:
                document = extract_xlsx(doc.file)
            case FileKind.JPEG | FileKind.PNG:
                document, stats = extract_image(
                    doc.file, engine, max_pages=settings.max_pdf_pages, check=check
                )
            case _:
                raise AppError(ErrorCode.UNSUPPORTED_EXTENSION, "Nieobsługiwany format dokumentu")
    except AppError:
        raise
    except Exception as exc:
        # Uszkodzony plik, który przeszedł walidację. W logu tylko typ wyjątku: komunikaty
        # bibliotek potrafią cytować fragmenty dokumentu.
        logger.warning("ekstrakcja nieudana: format=%s błąd=%s", doc.kind, type(exc).__name__)
        raise AppError(ErrorCode.DOCUMENT_UNREADABLE, "Nie udało się odczytać dokumentu") from exc
    finally:
        doc.file.seek(0)

    warnings = _ocr_warnings(stats)
    logger.info(
        "ekstrakcja: format=%s metoda=%s strony=%d bloki=%d czas_ms=%d ostrzeżenia=%s",
        doc.kind,
        document.source.method,
        len(document.pages),
        sum(len(p.blocks) for p in document.pages),
        int((clock() - started) * 1000),
        [w.code for w in warnings],
    )
    return ExtractionResult(document, warnings)


def _ocr_warnings(stats: OcrStats) -> list[ConversionWarning]:
    warnings: list[ConversionWarning] = []
    if stats.failed:
        warnings.append(
            ConversionWarning(
                code="W11_OCR_UNAVAILABLE",
                message="Nie udało się rozpoznać tekstu (OCR) na stronach: "
                f"{_pages(stats.failed)}. Formularz może być niepełny.",
            )
        )
    low = sorted(n for n, conf in stats.confidences.items() if conf < LOW_OCR_CONFIDENCE)
    if low:
        warnings.append(
            ConversionWarning(
                code="W12_LOW_OCR_CONFIDENCE",
                message=f"Niska jakość rozpoznania tekstu (OCR) na stronach: {_pages(low)}. "
                "Sprawdź etykiety pól.",
            )
        )
    return warnings


def _pages(numbers: list[int]) -> str:
    return ", ".join(str(n) for n in numbers)
