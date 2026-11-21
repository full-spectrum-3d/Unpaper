"""[4] Analiza LLM: DocumentModel → FormDraft (spec §5.4, projekt LLM §5.4, §5.7).

`analyze()` nigdy nie przerywa żądania z powodu modelu: przy timeoucie, braku
serwera albo niepoprawnej odpowiedzi zwraca `AnalysisResult` z `draft=None`
i ostrzeżeniem `W01_LLM_FALLBACK` - formularz zbuduje się wtedy bez szkicu.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from typing import Literal

from pydantic import ValidationError

from app.core.config import Settings
from app.models.document import DocumentModel
from app.models.draft import FormDraft, LlmDraft, llm_schema
from app.models.warning import ConversionWarning
from app.pipeline.draft_merge import merge_drafts, split_prompt_text
from app.pipeline.draft_normalize import normalize_draft
from app.pipeline.draft_repair import repair_draft
from app.pipeline.llm_client import (
    ChatMessage,
    LlmClient,
    LlmReply,
    LlmTimeoutError,
    LlmUnavailableError,
)

logger = logging.getLogger(__name__)

FallbackReason = Literal["timeout", "unavailable", "invalid_output", "empty_document"]

MIN_CALL_BUDGET_S = 30
CHARS_PER_TOKEN = 3
RESPONSE_RESERVE_TOKENS = 2048
MIN_CHUNK_CHARS = 1000
RETRY_BUDGET_FACTOR = 1.2

_FALLBACK_MESSAGES: dict[FallbackReason, str] = {
    "timeout": "model nie odpowiedział w dostępnym czasie",
    "unavailable": "model jest niedostępny",
    "invalid_output": "model zwrócił niepoprawny szkic",
    "empty_document": "dokument nie zawiera tekstu do analizy",
}


@dataclass
class AnalysisResult:
    draft: FormDraft | None
    model: str
    duration_ms: int = 0
    retries: int = 0
    fallback: bool = False
    fallback_reason: FallbackReason | None = None
    prompt_tokens: int = 0
    output_tokens: int = 0
    warnings: list[ConversionWarning] = field(default_factory=list)

    def _add(self, reply: LlmReply) -> None:
        self.duration_ms += reply.duration_ms
        self.prompt_tokens += reply.prompt_tokens
        self.output_tokens += reply.output_tokens

    def _fail(self, reason: FallbackReason) -> AnalysisResult:
        self.draft = None
        self.fallback = True
        self.fallback_reason = reason
        self.warnings.insert(
            0,
            ConversionWarning(
                code="W01_LLM_FALLBACK",
                message=f"Formularz zbudowany bez analizy AI: {_FALLBACK_MESSAGES[reason]}.",
            ),
        )
        return self


@cache
def load_system_prompt() -> str:
    """Prompt systemowy z `app/resources/prompts/system.md`."""
    return (files("app") / "resources" / "prompts" / "system.md").read_text(encoding="utf-8")


async def analyze(
    doc: DocumentModel,
    settings: Settings,
    client: LlmClient,
    *,
    deadline: float,
    clock: Callable[[], float] = time.monotonic,
) -> AnalysisResult:
    """Szkic formularza z dokumentu. `deadline` to `clock()` końca budżetu żądania."""
    result = AnalysisResult(draft=None, model=settings.llm_model)
    try:
        return await _analyze(doc, settings, client, result, deadline, clock)
    finally:
        logger.info(
            "analiza LLM: model=%s czas=%d ms wejście=%d wyjście=%d ponowienia=%d fallback=%s",
            result.model,
            result.duration_ms,
            result.prompt_tokens,
            result.output_tokens,
            result.retries,
            result.fallback_reason,
        )


async def _analyze(
    doc: DocumentModel,
    settings: Settings,
    client: LlmClient,
    result: AnalysisResult,
    deadline: float,
    clock: Callable[[], float],
) -> AnalysisResult:
    text = doc.to_prompt_text()
    if not text.strip():
        return result._fail("empty_document")

    system = load_system_prompt()
    max_chars = (settings.llm_num_ctx - RESPONSE_RESERVE_TOKENS) * CHARS_PER_TOKEN - len(system)
    chunks = split_prompt_text(text, max(max_chars, MIN_CHUNK_CHARS))
    if len(chunks) == 1:
        outcome = await _single(client, settings, result, system, text, deadline, clock)
    else:
        outcome = await _chunked(client, settings, result, system, chunks, deadline, clock)
    if isinstance(outcome, str):
        return result._fail(outcome)

    try:
        result.draft, warnings = normalize_draft(outcome, doc)
    except ValidationError:
        logger.exception("normalizacja dała niepoprawny szkic")
        return result._fail("invalid_output")
    result.warnings.extend(warnings)
    return result


def _messages(system: str, text: str, note: str = "") -> list[ChatMessage]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{note}<dokument>\n{text}\n</dokument>"},
    ]


async def _single(
    client: LlmClient,
    settings: Settings,
    result: AnalysisResult,
    system: str,
    text: str,
    deadline: float,
    clock: Callable[[], float],
) -> FormDraft | FallbackReason:
    """Cały dokument w jednym wywołaniu; jedna ponowna próba, jeśli starczy budżetu.

    Ponawiamy tylko odpowiedź niezgodną ze schematem (np. ucięty JSON). Błędy
    odwołań między polami poprawia `repair_draft` bez kolejnego wywołania.
    """
    messages = _messages(system, text)
    outcome = await _call(client, settings, result, messages, deadline, clock)
    if isinstance(outcome, str):
        return outcome
    reply, parsed = outcome
    if not isinstance(parsed, ValidationError):
        return parsed

    first_call_s = reply.duration_ms / 1000
    if deadline - clock() < first_call_s * RETRY_BUDGET_FACTOR:
        return "invalid_output"
    result.retries += 1
    messages = [
        *messages,
        {"role": "assistant", "content": reply.content},
        {"role": "user", "content": _retry_message(parsed)},
    ]
    outcome = await _call(client, settings, result, messages, deadline, clock)
    if isinstance(outcome, str):
        return outcome
    _, parsed = outcome
    return "invalid_output" if isinstance(parsed, ValidationError) else parsed


async def _chunked(
    client: LlmClient,
    settings: Settings,
    result: AnalysisResult,
    system: str,
    chunks: list[str],
    deadline: float,
    clock: Callable[[], float],
) -> FormDraft | FallbackReason:
    """Fragmenty kolejno, bez ponownych prób; nieudany fragment (poza pierwszym) pomijamy."""
    drafts: list[FormDraft] = []
    for i, chunk in enumerate(chunks):
        note = f"Fragment {i + 1} z {len(chunks)} dokumentu.\n"
        outcome = await _call(
            client, settings, result, _messages(system, chunk, note), deadline, clock
        )
        failure: FallbackReason | None = None
        if isinstance(outcome, str):
            failure = outcome
        elif isinstance(outcome[1], ValidationError):
            failure = "invalid_output"
        else:
            drafts.append(outcome[1])
        if failure is None:
            continue
        if i == 0:
            return failure
        result.warnings.append(
            ConversionWarning(
                code="W14_PARTIAL_ANALYSIS",
                message=f"Fragment {i + 1} z {len(chunks)} dokumentu nie został przeanalizowany "
                f"({_FALLBACK_MESSAGES[failure]}) - sprawdź, czy formularz jest kompletny.",
                path=f"chunk[{i}]",
            )
        )
        if failure == "timeout":
            break
    try:
        return merge_drafts(drafts)
    except ValidationError:
        logger.exception("łączenie fragmentów dało niepoprawny szkic")
        return "invalid_output"


async def _call(
    client: LlmClient,
    settings: Settings,
    result: AnalysisResult,
    messages: list[ChatMessage],
    deadline: float,
    clock: Callable[[], float],
) -> tuple[LlmReply, FormDraft | ValidationError] | FallbackReason:
    """Jedno wywołanie modelu z walidacją i naprawą; przy błędzie wywołania zwraca przyczynę."""
    remaining = deadline - clock()
    if remaining < MIN_CALL_BUDGET_S:
        return "timeout"
    try:
        reply = await client.chat(
            model=result.model,
            messages=messages,
            schema=llm_schema(),
            timeout_s=min(settings.llm_timeout_s, remaining),
        )
    except LlmTimeoutError:
        return "timeout"
    except LlmUnavailableError as exc:
        logger.warning("model niedostępny: %s", exc)
        return "unavailable"
    result._add(reply)
    try:
        draft, warnings = repair_draft(LlmDraft.model_validate_json(reply.content))
    except ValidationError as exc:
        return reply, exc
    result.warnings.extend(warnings)
    return reply, draft


def _retry_message(error: ValidationError) -> str:
    lines = []
    for item in error.errors(include_url=False):
        loc = ".".join(str(part) for part in item["loc"]) or "szkic"
        lines.append(f"- {loc}: {item['msg']}")
    return (
        "Odpowiedź nie spełnia schematu. Popraw błędy i zwróć cały szkic ponownie:\n"
        + "\n".join(lines)
    )
