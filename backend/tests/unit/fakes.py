"""Atrapy do testów analizy LLM: kontrolowany zegar i klient zwracający zadane odpowiedzi."""

import json
from pathlib import Path
from typing import Any

from app.pipeline.llm_client import ChatMessage, LlmReply

LLM_RESPONSES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def reply(content: str, duration_ms: int = 60_000, prompt: int = 700, out: int = 300) -> LlmReply:
    return LlmReply(
        content=content, prompt_tokens=prompt, output_tokens=out, duration_ms=duration_ms
    )


def fixture_reply(name: str, duration_ms: int = 60_000) -> LlmReply:
    envelope = json.loads((LLM_RESPONSES / f"{name}.json").read_text(encoding="utf-8"))
    return reply(
        envelope["message"]["content"],
        duration_ms=duration_ms,
        prompt=envelope["prompt_eval_count"],
        out=envelope["eval_count"],
    )


class FakeLlmClient:
    def __init__(
        self,
        replies: list[LlmReply | Exception] | None = None,
        clock: FakeClock | None = None,
        models: set[str] | Exception | None = None,
    ) -> None:
        self.replies = list(replies or [])
        self.clock = clock or FakeClock()
        self.models = {"qwen3:8b", "qwen3:4b"} if models is None else models
        self.calls: list[dict[str, Any]] = []
        self.warmed: list[str] = []

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        timeout_s: float,
    ) -> LlmReply:
        self.calls.append(
            {"model": model, "messages": list(messages), "schema": schema, "timeout_s": timeout_s}
        )
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        self.clock.now += item.duration_ms / 1000
        return item

    async def list_models(self) -> set[str]:
        if isinstance(self.models, Exception):
            raise self.models
        return self.models

    async def warm_up(self, model: str) -> None:
        self.warmed.append(model)

    async def aclose(self) -> None:
        return None
