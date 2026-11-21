"""Cały pipeline dla jednego zwalidowanego pliku: [2] normalizacja … [6] weryfikacja.

`convert_upload` łączy etapy ze spec §5 i składa raport konwersji (§6.2). Nie zna HTTP:
endpoint `/forms/convert` odbiera i waliduje plik ([1]), pilnuje limitu równoległych
zadań i zamienia wynik na odpowiedź. Ten sam kod może wywołać skrypt wsadowy.

Zasady:
- `deadline` (wartość `clock()`) liczy się od wejścia żądania i obejmuje wszystkie etapy.
  Ekstrakcja po terminie kończy się `PROCESSING_TIMEOUT`, a analiza LLM przechodzi wtedy
  na szkic z reguł (`analyze` nie rzuca z powodu modelu).
- Etapy obciążające CPU (ekstrakcja, budowa, weryfikacja) działają w puli wątków.
- Wynik zawsze przechodzi weryfikację. Gdy po autonaprawie zostają błędy, budujemy
  formularz zastępczy, bo użytkownik ma dostać strukturalnie poprawny JSON (spec §5.6).
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

import anyio.to_thread

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.document import DocumentModel
from app.models.draft import FormDraft
from app.models.form import FormJson
from app.models.warning import ConversionWarning
from app.pipeline.analyze import AnalysisResult, analyze
from app.pipeline.build import BuildOptions, BuildResult, build_fallback, build_form
from app.pipeline.converter import Converter
from app.pipeline.extract import ExtractionResult, OcrEngine, extract
from app.pipeline.llm_client import LlmClient
from app.pipeline.normalize import normalize
from app.pipeline.upload_validation import UploadLimits, ValidatedUpload
from app.pipeline.verify import VerifyResult, verify_form

logger = logging.getLogger(__name__)

SECTION_TYPES = frozenset({"SECTION", "REPEATING_SECTION"})


@dataclass
class ConversionResult:
    form: FormJson
    """JSON w formacie importu Generatora Formularzy (spec §7)."""
    report: dict[str, Any]
    """Raport konwersji (spec §6.2)."""
    warnings: list[ConversionWarning]


def upload_limits(settings: Settings) -> UploadLimits:
    return UploadLimits.from_megabytes(
        max_file_size_mb=settings.max_file_size_mb,
        spool_max_mb=settings.spool_max_mb,
        max_uncompressed_mb=settings.max_uncompressed_mb,
        max_pdf_pages=settings.max_pdf_pages,
        max_image_pixels=settings.max_image_pixels,
    )


async def convert_upload(
    upload: ValidatedUpload,
    *,
    settings: Settings,
    client: LlmClient,
    converter: Converter | None,
    deadline: float,
    clock: Callable[[], float] = time.monotonic,
    ocr: OcrEngine | None = None,
) -> ConversionResult:
    """Plik po walidacji → formularz i raport. Błędy pliku i timeouty to `AppError`."""
    started = clock()
    timings: dict[str, int] = {}

    def lap(name: str, since: float) -> float:
        now = clock()
        timings[name] = int((now - since) * 1000)
        return now

    mark = started
    with await normalize(upload, converter, upload_limits(settings)) as doc:
        mark = lap("normalizeMs", mark)
        _check_deadline(clock, deadline, "Przekroczono czas przetwarzania przed ekstrakcją")
        extraction: ExtractionResult = await anyio.to_thread.run_sync(
            partial(extract, doc, settings, ocr=ocr, deadline=deadline, clock=clock)
        )
        converted = doc.converted
    mark = lap("extractMs", mark)

    analysis = await analyze(extraction.document, settings, client, deadline=deadline, clock=clock)
    mark = lap("analyzeMs", mark)

    options = BuildOptions.from_settings(settings)
    built, checked, rebuilt = await anyio.to_thread.run_sync(
        partial(_build_and_verify, analysis.draft, options)
    )
    lap("buildMs", mark)

    warnings = [*extraction.warnings, *analysis.warnings, *built.warnings, *checked.warnings]
    if rebuilt:
        warnings.append(
            ConversionWarning(
                code="W27_FORM_REBUILT",
                message="Zbudowany formularz nie przeszedł weryfikacji - zwrócono formularz "
                "zastępczy z sekcjami predefiniowanymi. Uzupełnij przedmiot wniosku ręcznie.",
            )
        )
    duration_ms = int((clock() - started) * 1000)
    report = _report(
        upload, extraction.document, converted, analysis, built, checked, warnings, timings
    )
    report["durationMs"] = duration_ms
    logger.info(
        "konwersja: plik=%s rozmiar=%d format=%s czas_ms=%d etapy=%s fallback=%s "
        "przebudowa=%s ostrzeżenia=%s",
        _name_hash(upload.filename),
        upload.size_bytes,
        upload.kind,
        duration_ms,
        timings,
        analysis.fallback_reason,
        rebuilt,
        sorted({w.code for w in warnings}),
    )
    return ConversionResult(form=checked.form, report=report, warnings=warnings)


def _check_deadline(clock: Callable[[], float], deadline: float, detail: str) -> None:
    if clock() > deadline:
        raise AppError(ErrorCode.PROCESSING_TIMEOUT, detail)


def _build_and_verify(
    draft: FormDraft | None, options: BuildOptions
) -> tuple[BuildResult, VerifyResult, bool]:
    built = build_form(draft, options) if draft is not None else build_fallback(options=options)
    checked = verify_form(built.form.to_import_json(), autofix=True)
    if checked.valid:
        return built, checked, False
    logger.error(
        "formularz po autonaprawie ma błędy: %s - budujemy formularz zastępczy",
        sorted({issue.code for issue in checked.errors}),
    )
    title = draft.title if draft is not None else None
    authority = draft.authority_name if draft is not None else ""
    fallback = build_fallback(title=title, authority_name=authority, options=options)
    fallback_checked = verify_form(fallback.form.to_import_json(), autofix=True)
    if not fallback_checked.valid:
        raise AppError(ErrorCode.INTERNAL_ERROR, "Nie udało się zbudować poprawnego formularza")
    return fallback, fallback_checked, True


def _report(
    upload: ValidatedUpload,
    document: DocumentModel,
    converted: bool,
    analysis: AnalysisResult,
    built: BuildResult,
    checked: VerifyResult,
    warnings: list[ConversionWarning],
    timings: dict[str, int],
) -> dict[str, Any]:
    return {
        "sourceFile": {
            "name": upload.filename,
            "mime": upload.mime,
            "sizeBytes": upload.size_bytes,
            "pages": upload.page_count or document.source.pages,
            "decrypted": upload.decrypted,
        },
        "extraction": {
            "method": document.source.method,
            "convertedToOpenXml": converted,
            "ocrMeanConfidence": document.ocr_mean_confidence,
            "blocks": sum(len(page.blocks) for page in document.pages),
        },
        "llm": {
            "model": analysis.model,
            "durationMs": analysis.duration_ms,
            "retries": analysis.retries,
            "fallback": analysis.fallback,
            "fallbackReason": analysis.fallback_reason,
            "ruleBasedDraft": any(w.code == "W24_RULE_BASED_DRAFT" for w in analysis.warnings),
            "promptTokens": analysis.prompt_tokens,
            "outputTokens": analysis.output_tokens,
        },
        "stats": form_stats(checked.form),
        "dictionaryProposals": [
            proposal.model_dump(by_alias=True, mode="json")
            for proposal in built.dictionary_proposals
        ],
        "warnings": [w.model_dump(exclude_none=True) for w in warnings],
        "fixes": [issue.to_dict() for issue in checked.fixes],
        "timings": timings,
    }


def form_stats(form: FormJson) -> dict[str, int]:
    """Liczba stron, sekcji, pól i stanów JSONata w formularzu."""
    sections = fields = states = 0
    for tab in form.get("tabs", []):
        for question in tab.get("questions", []):
            field = question.get("field", {})
            states += len(field.get("states") or [])
            if field.get("type") not in SECTION_TYPES:
                fields += 1
                continue
            sections += 1
            for child in field.get("repeatingSectionGrid") or []:
                fields += 1
                states += len(child.get("field", {}).get("states") or [])
    return {
        "tabs": len(form.get("tabs", [])),
        "sections": sections,
        "fields": fields,
        "states": states,
    }


def _name_hash(name: str) -> str:
    """Nazwa pliku w logach tylko jako skrót (spec §10.3)."""
    return hashlib.sha256(name.encode()).hexdigest()[:12]
