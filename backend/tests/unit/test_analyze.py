import json
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.document import DocumentModel
from app.models.draft import LlmDraft, llm_schema
from app.pipeline.analyze import AnalysisResult, analyze, load_system_prompt, prompt_messages
from app.pipeline.draft_repair import repair_draft
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


def _invalid_ref() -> LlmReply:
    """Warunek widoczności wskazuje nieistniejące pole f9 - naprawialne w kodzie."""
    return fixture_reply("wniosek1_invalid_ref")


def _invalid(duration_ms: int = 60_000) -> LlmReply:
    """Odpowiedź niezgodna ze schematem (nieznany `kind`) - wymaga ponownej próby."""
    content = json.loads(_valid().content)
    content["subject_pages"][0]["sections"][0]["fields"][0]["kind"] = "textarea"
    return reply(json.dumps(content, ensure_ascii=False), duration_ms=duration_ms)


async def test_valid_reply_returns_draft() -> None:
    r, _ = await _run([_valid()])
    assert r.draft is not None and r.draft.authority_name == "Wójt Gminy Elbląg"
    assert (r.fallback, r.retries, r.model) == (False, 0, "qwen3:8b")
    assert (r.prompt_tokens, r.output_tokens, r.duration_ms) == (700, 300, 60_000)


async def test_request_contains_document_and_schema() -> None:
    _, client = await _run([_valid()])
    messages = client.calls[0]["messages"]
    assert messages[0] == {"role": "system", "content": load_system_prompt()}
    assert messages[:3] == prompt_messages("x")[:3]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[3]["content"].startswith("<dokument>\n=== strona 1")
    assert messages[3]["content"].endswith("\n</dokument>")
    assert client.calls[0]["schema"] == llm_schema()


async def test_invalid_reference_repaired_without_retry() -> None:
    r, client = await _run([_invalid_ref()])
    assert len(client.calls) == 1 and r.retries == 0 and r.draft is not None
    assert [w.code for w in r.warnings] == ["W21_CONDITION_REMOVED"]
    assert "f9" in r.warnings[0].message
    assert all(not f.visible_when for _, f in r.draft.iter_fields())


async def test_schema_error_then_valid_retries_once() -> None:
    r, client = await _run([_invalid(), _valid()])
    assert r.retries == 1 and r.draft is not None and not r.fallback
    assert "kind" in client.calls[1]["messages"][-1]["content"]
    assert client.calls[1]["messages"][-2]["role"] == "assistant"
    assert r.output_tokens == 600


async def test_invalid_twice_falls_back() -> None:
    r, _ = await _run([_invalid(), _invalid()])
    assert (r.fallback, r.fallback_reason, r.retries) == (True, "invalid_output", 1)
    assert [w.code for w in r.warnings][:2] == ["W01_LLM_FALLBACK", "W24_RULE_BASED_DRAFT"]
    assert r.draft is not None
    assert [f.label for _, f in r.draft.iter_fields()] == [
        "Miejscowość",
        "Ulica",
        "Numer ewidencyjny działki",
        "Obręb",
    ]


async def test_fallback_without_fields_has_no_draft() -> None:
    doc = DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [
                {"number": 1, "blocks": [{"id": "b1", "kind": "paragraph", "text": "Tekst"}]}
            ],
        }
    )
    r, _ = await _run([LlmTimeoutError("slow")], doc=doc)
    assert (r.draft, r.fallback_reason) == (None, "timeout")
    assert [w.code for w in r.warnings] == ["W01_LLM_FALLBACK"]


async def test_truncated_json_is_invalid_output() -> None:
    r, _ = await _run([reply('{"title": "Wniosek o'), reply('{"title": "Wniosek o')])
    assert (r.fallback, r.fallback_reason) == (True, "invalid_output")


async def test_no_retry_when_budget_too_small() -> None:
    r, client = await _run([_invalid(duration_ms=100_000)], deadline=150)
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
    r, _ = await _run([LlmUnavailableError("model 'qwen3:8b' not found")])
    assert (r.fallback, r.fallback_reason) == (True, "unavailable")


async def test_model_from_settings() -> None:
    r, client = await _run([_valid()], settings=_settings(llm_model="bielik:11b"))
    assert r.model == "bielik:11b" and client.calls[0]["model"] == "bielik:11b"


async def test_normalization_warnings_in_result() -> None:
    content = json.loads(_valid().content)
    content["title"] = "WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO NIERUCHOMOŚCI"
    r, _ = await _run([reply(json.dumps(content, ensure_ascii=False))])
    assert r.draft is not None
    assert r.draft.title == "Wniosek o ustalenie numeru porządkowego nieruchomości"
    assert [w.code for w in r.warnings] == ["W16_TITLE_CASE_NORMALIZED"]


def _long_doc(pages: int = 3, chars: int = 2500) -> DocumentModel:
    line = "Miejscowość [POLE] Ulica [POLE] Numer ewidencyjny działki [POLE] Obręb [POLE] "
    text = (line * (chars // len(line) + 1))[:chars]
    return DocumentModel.model_validate(
        {
            "source": {"method": "pdf_text", "pages": pages},
            "pages": [
                {"number": n, "blocks": [{"id": f"b{n}", "kind": "paragraph", "text": text}]}
                for n in range(1, pages + 1)
            ],
        }
    )


CHUNKED = _settings(llm_num_ctx=5120)  # ok. 4300 znaków na fragment = 1 strona


async def test_long_document_chunked() -> None:
    r, client = await _run([_valid(), _valid(), _valid()], settings=CHUNKED, doc=_long_doc())
    assert len(client.calls) == 3
    assert "Fragment 2 z 3" in client.calls[1]["messages"][3]["content"]
    assert r.draft is not None and not r.fallback and r.retries == 0
    assert len(list(r.draft.iter_fields())) == 4


async def test_failed_later_chunk_gives_partial() -> None:
    r, _ = await _run([_valid(), _invalid(), _valid()], settings=CHUNKED, doc=_long_doc())
    assert r.draft is not None and not r.fallback
    w14 = [w for w in r.warnings if w.code == "W14_PARTIAL_ANALYSIS"]
    assert [w.path for w in w14] == ["chunk[1]"]


async def test_chunking_stops_when_budget_runs_out() -> None:
    r, client = await _run(
        [_valid(), _valid(), _valid()], settings=CHUNKED, doc=_long_doc(), deadline=140
    )
    assert len(client.calls) == 2 and r.draft is not None
    assert [w.path for w in r.warnings if w.code == "W14_PARTIAL_ANALYSIS"] == ["chunk[2]"]


async def test_failed_first_chunk_falls_back() -> None:
    r, client = await _run([_invalid()], settings=CHUNKED, doc=_long_doc())
    assert len(client.calls) == 1 and r.fallback_reason == "invalid_output"


async def test_merge_failure_is_invalid_output_not_exception(monkeypatch: Any) -> None:
    import app.pipeline.analyze as module
    from app.models.draft import FormDraft

    def broken(drafts: Any) -> FormDraft:
        return FormDraft.model_validate({})  # rzuca ValidationError jak zepsute łączenie

    monkeypatch.setattr(module, "merge_drafts", broken)
    r, _ = await _run([_valid(), _valid(), _valid()], settings=CHUNKED, doc=_long_doc())
    assert (r.fallback, r.fallback_reason) == (True, "invalid_output")


def test_prompt_example_is_a_clean_draft() -> None:
    example = prompt_messages("")[2]["content"]
    assert "\n" not in example and ": " not in example
    draft, warnings = repair_draft(LlmDraft.model_validate_json(example))
    assert warnings == [] and len(list(draft.iter_fields())) == 9
    assert "Oświadczam" in prompt_messages("")[1]["content"] and draft.statements == []
