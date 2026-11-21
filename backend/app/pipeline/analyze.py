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

from app.core.config import LlmMode, Settings
from app.models.document import DocumentModel
from app.models.draft import FormDraft, llm_schema
from app.models.warning import ConversionWarning
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
    mode: LlmMode
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
    mode: LlmMode | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> AnalysisResult:
    """Szkic formularza z dokumentu. `deadline` to `clock()` końca budżetu żądania."""
    mode = mode or settings.llm_default_mode
    result = AnalysisResult(draft=None, mode=mode, model=settings.llm_model_for(mode))
    try:
        return await _analyze(doc, settings, client, result, deadline, clock)
    finally:
        logger.info(
            "analiza LLM: tryb=%s model=%s czas=%d ms wejście=%d wyjście=%d ponowienia=%d "
            "fallback=%s",
            result.mode,
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

    messages: list[ChatMessage] = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": f"<dokument>\n{text}\n</dokument>"},
    ]
    outcome = await _call(client, settings, result, messages, deadline, clock)
    if isinstance(outcome, str):
        return result._fail(outcome)
    reply, parsed = outcome

    if isinstance(parsed, ValidationError):
        first_call_s = reply.duration_ms / 1000
        can_retry = (
            result.mode == "accurate" and deadline - clock() >= first_call_s * RETRY_BUDGET_FACTOR
        )
        if not can_retry:
            return result._fail("invalid_output")
        result.retries += 1
        messages = [
            *messages,
            {"role": "assistant", "content": reply.content},
            {"role": "user", "content": _retry_message(parsed)},
        ]
        outcome = await _call(client, settings, result, messages, deadline, clock)
        if isinstance(outcome, str):
            return result._fail(outcome)
        _, parsed = outcome
        if isinstance(parsed, ValidationError):
            return result._fail("invalid_output")

    result.draft = parsed
    return result


async def _call(
    client: LlmClient,
    settings: Settings,
    result: AnalysisResult,
    messages: list[ChatMessage],
    deadline: float,
    clock: Callable[[], float],
) -> tuple[LlmReply, FormDraft | ValidationError] | FallbackReason:
    """Jedno wywołanie modelu z walidacją; przy błędzie wywołania zwraca przyczynę fallbacku."""
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
        return reply, FormDraft.model_validate_json(reply.content)
    except ValidationError as exc:
        return reply, exc


def _retry_message(error: ValidationError) -> str:
    lines = []
    for item in error.errors(include_url=False):
        loc = ".".join(str(part) for part in item["loc"]) or "szkic"
        lines.append(f"- {loc}: {item['msg']}")
    return (
        "Odpowiedź nie spełnia schematu. Popraw błędy i zwróć cały szkic ponownie:\n"
        + "\n".join(lines)
    )
