"""Test na żywym modelu: `uv run pytest -m llm -s tests/integration` (wymaga Ollamy)."""

import os
import time
from pathlib import Path

import pytest

from app.core.config import LlmMode, Settings
from app.models.document import DocumentModel
from app.pipeline.analyze import analyze
from app.pipeline.draft_normalize import matches_text
from app.pipeline.llm_client import OllamaClient

DOC = DocumentModel.model_validate_json(
    (Path(__file__).parent.parent / "fixtures" / "documents" / "wniosek1.json").read_text(
        encoding="utf-8"
    )
)
EXPECTED = ["Miejscowość", "Ulica", "Numer ewidencyjny działki", "Obręb"]


@pytest.mark.llm
@pytest.mark.parametrize("mode", ["accurate", "fast"])
async def test_wniosek1_live(mode: LlmMode) -> None:
    settings = Settings(
        app_env="development",
        auth_enabled=False,
        _env_file=None,
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434"),
    )
    client = OllamaClient(settings)
    try:
        r = await analyze(DOC, settings, client, deadline=time.monotonic() + 600, mode=mode)
    finally:
        await client.aclose()
    print(
        f"\n{mode}: {r.duration_ms} ms, in={r.prompt_tokens}, out={r.output_tokens}, "
        f"retries={r.retries}, warnings={[w.code for w in r.warnings]}"
    )
    assert r.draft is not None and not r.fallback
    labels = [f.label for _, f in r.draft.iter_fields()]
    d = r.draft
    print(f"{mode}: {d.title!r} / {d.authority_kind} {d.authority_name!r} / {labels}")
    found = sum(any(matches_text(e, label, 0.6) for label in labels) for e in EXPECTED)
    assert found >= 3
    assert r.draft.authority_kind == "ORGAN"
