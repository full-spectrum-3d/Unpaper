"""Atrapy do testów: zegar, klient LLM zwracający zadane odpowiedzi, runner konwertera."""

import asyncio
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import docx
import openpyxl

from app.pipeline.converter import ConverterTimeoutError, RunResult
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


RunnerBehavior = Literal[
    "ok", "no_output", "other_name", "empty", "exit1", "garbage", "timeout", "oserror", "hang"
]


def office_bytes(ext: str) -> bytes:
    """Mały, poprawny DOCX albo XLSX."""
    buffer = io.BytesIO()
    if ext == "docx":
        document = docx.Document()
        document.add_paragraph("Wniosek")
        document.save(buffer)
    else:
        workbook = openpyxl.Workbook()
        workbook.active["A1"] = "Wniosek"  # type: ignore[index]
        workbook.save(buffer)
    return buffer.getvalue()


class FakeRunner:
    """Udaje `soffice --convert-to`: zapisuje wynik do `--outdir` według `behavior`."""

    def __init__(self, behavior: RunnerBehavior = "ok") -> None:
        self.behavior = behavior
        self.calls: list[list[str]] = []
        self.envs: list[dict[str, str]] = []
        self.profile_seeded: list[bool] = []
        self.started = asyncio.Event()

    async def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        timeout_s: float,
    ) -> RunResult:
        args = list(argv)
        self.calls.append(args)
        self.envs.append(dict(env))
        profile = Path.from_uri(args[1].removeprefix("-env:UserInstallation="))
        self.profile_seeded.append((profile / "user" / "registrymodifications.xcu").is_file())
        self.started.set()

        outdir = Path(args[args.index("--outdir") + 1])
        ext = args[args.index("--convert-to") + 1].split(":")[0]
        stem = Path(args[-1]).stem
        match self.behavior:
            case "ok":
                (outdir / f"{stem}.{ext}").write_bytes(office_bytes(ext))
            case "other_name":
                (outdir / f"wynik.{ext}").write_bytes(office_bytes(ext))
            case "empty":
                (outdir / f"{stem}.{ext}").write_bytes(b"")
            case "garbage":
                (outdir / f"{stem}.{ext}").write_bytes(b"not a zip")
            case "exit1":
                return RunResult(1, b"Error: source file could not be loaded")
            case "timeout":
                raise ConverterTimeoutError("przekroczono")
            case "oserror":
                raise FileNotFoundError("soffice")
            case "hang":
                await asyncio.Event().wait()
            case "no_output":
                pass
        return RunResult(0, b"")
