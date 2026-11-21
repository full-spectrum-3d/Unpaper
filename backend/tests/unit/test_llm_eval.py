from pathlib import Path
from typing import Any

import docx
import pytest

from app.core.config import Settings
from app.models.draft import FormDraft
from llm_eval.build_case import build_document
from llm_eval.metrics import score_draft, similarity
from llm_eval.run import RULES, load_cases, run_case

CASES = load_cases()


def _draft(*labels: tuple[str, str]) -> FormDraft:
    return FormDraft.model_validate(
        {
            "title": "Wniosek o ustalenie numeru porządkowego nieruchomości",
            "authority_kind": "ORGAN",
            "authority_name": "Wójt Gminy Elbląg",
            "applicant_kinds": ["SELF"],
            "subject_pages": [
                {
                    "title": "P",
                    "sections": [
                        {
                            "title": "S",
                            "repeating": False,
                            "fields": [
                                {"id": f"f{i}", "label": label, "kind": kind, "required": True}
                                for i, (label, kind) in enumerate(labels, 1)
                            ],
                        }
                    ],
                }
            ],
        }
    )


def test_cases_are_complete() -> None:
    assert len(CASES) == 9
    for case in CASES:
        assert case["doc"].to_prompt_text(), case["slug"]
        assert case["expected"]["title"] and case["expected"]["fields"], case["slug"]


def test_holdout_is_complete() -> None:
    holdout = load_cases(set_name="holdout")
    assert len(holdout) >= 6
    assert not {c["slug"] for c in holdout} & {c["slug"] for c in CASES}
    for case in holdout:
        assert case["doc"].to_prompt_text(), case["slug"]
        assert case["expected"]["title"] and case["expected"]["fields"], case["slug"]
        assert any(not f["optional"] for f in case["expected"]["fields"]), case["slug"]


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("W miejscowości", "Miejscowość"),
        ("Przy ulicy", "Ulica"),
        ("Nr działki", "Numer działki"),
        ("Termin wynajmu od", "Termin od"),
    ],
)
def test_similar_labels(a: str, b: str) -> None:
    assert similarity(a, b) >= 0.6


def test_different_labels() -> None:
    assert similarity("Rasa psa", "Data urodzenia psa") < 0.6


def test_score_counts_matches_extras_kinds_and_optional() -> None:
    expected: dict[str, Any] = {
        "title": "Wniosek o ustalenie numeru porządkowego nieruchomości",
        "authority_kind": "ORGAN",
        "authority_name": "Wójt Gminy Elbląg",
        "fields": [
            {"label": "Miejscowość", "kind": ["short_text"], "aliases": [], "optional": False},
            {"label": "Data", "kind": ["date"], "aliases": [], "optional": False},
            {"label": "Obręb", "kind": ["short_text"], "aliases": [], "optional": True},
        ],
    }
    score = score_draft(
        _draft(
            ("W miejscowości", "short_text"),
            ("Data", "short_text"),
            ("Obręb", "short_text"),
            ("Kolor", "short_text"),
        ),
        expected,
    )
    assert (score.expected, score.matched, score.kind_ok, score.extra) == (2, 2, 1, 1)
    assert score.title_ok and score.authority_ok and score.precision == 0.75
    assert score.extras == ["Kolor"] and score.wrong_kinds == ["Data: short_text (oczekiwano date)"]


def test_no_draft_scores_zero() -> None:
    score = score_draft(None, CASES[0]["expected"])
    assert score.matched == 0 and score.recall == 0 and score.title_ok is False


@pytest.mark.parametrize("case", CASES, ids=[c["slug"] for c in CASES])
async def test_rule_baseline_builds_valid_forms(case: dict[str, Any]) -> None:
    row = await run_case(case, RULES, None, None, 0)  # type: ignore[arg-type]
    assert row.get("form_valid", True), case["slug"]


def _settings() -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None)


def test_build_document_uses_real_extraction(tmp_path: Path) -> None:
    source = tmp_path / "wniosek.docx"
    document = docx.Document()
    document.add_paragraph("Imię psa: ………")
    document.save(str(source))

    doc = build_document(source, _settings())

    assert doc.source.method == "docx"
    blocks = [block for page in doc.pages for block in page.blocks]
    assert any(b.kind == "input_placeholder" or "Imię psa" in b.text for b in blocks)


def test_build_document_rejects_legacy_formats(tmp_path: Path) -> None:
    legacy = tmp_path / "stary.doc"
    legacy.write_bytes(b"x")
    with pytest.raises(ValueError, match="DOCX"):
        build_document(legacy, _settings())
