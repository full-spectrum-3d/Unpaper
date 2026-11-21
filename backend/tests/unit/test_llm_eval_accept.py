from typing import Any

from llm_eval.accept import aggregate, violations


def row(case: str, recall: float, precision: float, **kw: Any) -> dict[str, Any]:
    base = {
        "set": "holdout",
        "run": 1,
        "case": case,
        "model": "m",
        "recall": recall,
        "precision": precision,
        "fallback": False,
    }
    return {**base, **kw}


def agg(*rows: dict[str, Any]) -> list[dict[str, Any]]:
    return aggregate(list(rows))


def test_aggregate_means_and_range() -> None:
    (a,) = agg(row("x", 0.8, 0.5, run=1), row("x", 1.0, 0.7, run=2))
    assert a["recall"] == 0.9
    assert a["recall_min"] == 0.8
    assert a["recall_max"] == 1.0
    assert a["precision_min"] == 0.5
    assert a["runs"] == 2


def test_aggregate_counts_fallback_runs() -> None:
    (a,) = agg(row("x", 1.0, 1.0), row("x", 0.5, 1.0, run=2, fallback=True))
    assert a["recall"] == 0.75
    assert a["runs"] == 2


def test_aggregate_defaults_for_old_rows() -> None:
    old = {"case": "x", "model": "m", "recall": 0.5, "precision": 0.5}
    (a,) = aggregate([old])
    assert a["set"] == "cases"
    assert a["runs"] == 1


def test_violations_empty_when_equal() -> None:
    b = agg(row("a", 0.9, 0.9), row("c", 0.9, 0.9, set="cases"))
    assert violations(b, b) == []


def test_violations_holdout_mean_drop_over_2pp() -> None:
    b = agg(row("a", 0.9, 0.9), row("b", 0.9, 0.9))
    c = agg(row("a", 0.9, 0.87), row("b", 0.9, 0.87))
    v = violations(b, c)
    assert len(v) == 1
    assert "holdout" in v[0] and "precyzja" in v[0]


def test_violations_holdout_mean_drop_within_2pp_ok() -> None:
    b = agg(row("a", 0.9, 0.9))
    c = agg(row("a", 0.9, 0.89))
    assert violations(b, c) == []


def test_violations_single_holdout_doc_drop_over_10pp() -> None:
    b = agg(row("a", 0.9, 0.9), row("b", 0.8, 0.9))
    c = agg(row("a", 0.99, 0.9), row("b", 0.69, 0.9))
    v = violations(b, c)
    assert len(v) == 1
    assert "b" in v[0]


def test_violations_cases_mean_drop() -> None:
    b = agg(row("a", 0.9, 0.9, set="cases"))
    c = agg(row("a", 0.89, 0.9, set="cases"))
    v = violations(b, c)
    assert len(v) == 1 and "cases" in v[0] and "trafność" in v[0]


def test_violations_missing_case_in_baseline() -> None:
    b = agg(row("a", 0.9, 0.9))
    c = agg(row("a", 0.9, 0.9), row("new", 0.9, 0.9))
    v = violations(b, c)
    assert len(v) == 1
    assert "brak w stanie wyjściowym" in v[0] and "new" in v[0]


def test_violations_per_model() -> None:
    b = agg(row("a", 0.9, 0.9, model="m1"), row("a", 0.9, 0.9, model="m2"))
    c = agg(row("a", 0.5, 0.9, model="m1"))
    v = violations(b, c)
    assert v and all("m1" in s for s in v)
    assert not any("m2" in s for s in v)
