from typing import Any

import pytest

from app.models.draft import FormDraft
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
