from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.document import DocumentModel
from app.models.draft import llm_schema
from app.pipeline.analyze import AnalysisResult, analyze, load_system_prompt
from app.pipeline.llm_client import LlmReply, LlmTimeoutError, LlmUnavailableError
from tests.unit.fakes import FakeClock, FakeLlmClient, fixture_reply, reply

DOC = DocumentModel.model_validate_json(
    (Path(__file__).parent.parent / "fixtures" / "documents" / "wniosek1.json").read_text(
        encoding="utf-8"
    )
)


def _settings(**kw: Any) -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None, **kw)


SETTINGS = _settings()


async def _run(
    replies: list[LlmReply | Exception],
    *,
    deadline: float = 1000,
    settings: Settings = SETTINGS,
    doc: DocumentModel = DOC,
    **kw: Any,
) -> tuple[AnalysisResult, FakeLlmClient]:
    clock = FakeClock()
    client = FakeLlmClient(replies, clock)
    result = await analyze(doc, settings, client, deadline=deadline, clock=clock, **kw)
    return result, client


def _valid() -> LlmReply:
    return fixture_reply("wniosek1_valid")


def _invalid() -> LlmReply:
    return fixture_reply("wniosek1_invalid_ref")


async def test_valid_reply_returns_draft() -> None:
    r, _ = await _run([_valid()])
    assert r.draft is not None and r.draft.authority_name == "Wójt Gminy Elbląg"
    assert (r.fallback, r.retries, r.mode, r.model) == (False, 0, "accurate", "qwen3:8b")
    assert (r.prompt_tokens, r.output_tokens, r.duration_ms) == (700, 300, 60_000)


async def test_request_contains_document_and_schema() -> None:
    _, client = await _run([_valid()])
    messages = client.calls[0]["messages"]
    assert messages[0] == {"role": "system", "content": load_system_prompt()}
    assert messages[1]["role"] == "user"
    assert messages[1]["content"].startswith("<dokument>\n=== strona 1")
    assert messages[1]["content"].endswith("\n</dokument>")
    assert client.calls[0]["schema"] == llm_schema()


async def test_invalid_then_valid_retries_once() -> None:
    r, client = await _run([_invalid(), _valid()])
    assert r.retries == 1 and r.draft is not None and not r.fallback
    assert "f9" in client.calls[1]["messages"][-1]["content"]
    assert client.calls[1]["messages"][-2]["role"] == "assistant"
    assert r.output_tokens == 600


async def test_invalid_twice_falls_back() -> None:
    r, _ = await _run([_invalid(), _invalid()])
    assert (r.draft, r.fallback, r.fallback_reason, r.retries) == (None, True, "invalid_output", 1)
    assert r.warnings[0].code == "W01_LLM_FALLBACK"


async def test_truncated_json_is_invalid_output() -> None:
    r, _ = await _run([reply('{"title": "Wniosek o'), reply('{"title": "Wniosek o')])
    assert (r.fallback, r.fallback_reason) == (True, "invalid_output")


async def test_fast_mode_never_retries() -> None:
    r, client = await _run([_invalid()], mode="fast")
    assert len(client.calls) == 1 and client.calls[0]["model"] == "qwen3:4b"
    assert (r.mode, r.fallback_reason, r.retries) == ("fast", "invalid_output", 0)


async def test_no_retry_when_budget_too_small() -> None:
    r, client = await _run(
        [fixture_reply("wniosek1_invalid_ref", duration_ms=100_000)], deadline=150
    )
    assert len(client.calls) == 1 and r.fallback_reason == "invalid_output"


async def test_timeout_is_capped_by_deadline() -> None:
    _, client = await _run([_valid()], deadline=90)
    assert client.calls[0]["timeout_s"] == 90
    _, client = await _run([_valid()], deadline=1000)
    assert client.calls[0]["timeout_s"] == 240


async def test_exhausted_deadline_skips_llm() -> None:
    r, client = await _run([], deadline=10)
    assert client.calls == [] and (r.fallback, r.fallback_reason) == (True, "timeout")


async def test_empty_document_falls_back() -> None:
    doc = DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"id": "b1", "kind": "paragraph", "text": "KLAUZULA INFORMACYJNA"},
                        {"id": "b2", "kind": "paragraph", "text": "Administratorem jest…"},
                    ],
                }
            ],
        }
    )
    r, client = await _run([], doc=doc)
    assert client.calls == [] and r.fallback_reason == "empty_document"


async def test_timeout_falls_back() -> None:
    r, _ = await _run([LlmTimeoutError("slow")])
    assert (r.fallback, r.fallback_reason) == (True, "timeout")
    assert r.warnings[0].code == "W01_LLM_FALLBACK"


async def test_unavailable_falls_back() -> None:
    r, _ = await _run([LlmUnavailableError("model 'qwen3:4b' not found")], mode="fast")
    assert (r.fallback, r.fallback_reason) == (True, "unavailable")


async def test_default_mode_from_settings() -> None:
    r, client = await _run([_valid()], settings=_settings(llm_default_mode="fast"))
    assert r.mode == "fast" and client.calls[0]["model"] == "qwen3:4b"


async def test_normalization_warnings_in_result() -> None:
    import json

    content = json.loads(_valid().content)
    content["title"] = "WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO NIERUCHOMOŚCI"
    r, _ = await _run([reply(json.dumps(content, ensure_ascii=False))])
    assert r.draft is not None
    assert r.draft.title == "Wniosek o ustalenie numeru porządkowego nieruchomości"
    assert [w.code for w in r.warnings] == ["W16_TITLE_CASE_NORMALIZED"]
