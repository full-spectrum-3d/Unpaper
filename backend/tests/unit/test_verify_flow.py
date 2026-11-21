"""R07: flow dopuszcza rozgałęzienia, ale wymaga osiągalności, dojścia do FINISH i braku cykli."""

from typing import Any

from app.pipeline.issues import IssueCode
from app.pipeline.verify import verify_form


def _tab(tid: str, ttype: str = "MAIN") -> dict[str, Any]:
    field = {
        "id": f"{tid}-f",
        "type": "TEXT_BLOCK",
        "techName": f"tb_{tid}",
        "title": "",
        "description": "",
        "options": [],
        "validation": [],
        "readOnly": False,
        "repeatingSectionGrid": [],
        "states": [],
        "questionOrder": 0,
        "tooltipMessage": "",
    }
    section = {**field, "id": f"{tid}-s", "type": "SECTION", "techName": f"s_{tid}"}
    section["repeatingSectionGrid"] = [{"x": 0, "y": 0, "rows": 1, "cols": 3, "field": field}]
    question = {"x": 0, "y": 0, "rows": 1, "cols": 3, "field": section}
    return {"id": tid, "title": tid, "type": ttype, "questions": [question]}


def _form(links: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "tabs": [_tab("a"), _tab("b"), _tab("c"), _tab("z", "FINISH")],
        "flow": {
            "links": [{"id": f"l{n}", "source": s, "target": t} for n, (s, t) in enumerate(links)]
        },
    }


def _r07(form: dict[str, Any]) -> list[Any]:
    result = verify_form(form, autofix=False)
    return [i for i in result.errors if i.code == IssueCode.R07_FLOW]


LINEAR = [("a", "b"), ("b", "c"), ("c", "z")]
BRANCH = [("a", "b"), ("a", "c"), ("b", "c"), ("c", "z")]


def test_linear_flow_ok() -> None:
    assert _r07(_form(LINEAR)) == []


def test_branching_flow_ok() -> None:
    assert _r07(_form(BRANCH)) == []


def test_branch_skipping_page_ok() -> None:
    assert _r07(_form([("a", "b"), ("a", "c"), ("b", "z"), ("c", "z")])) == []


def test_unreachable_page_reported() -> None:
    assert _r07(_form([("a", "b"), ("b", "z")]))


def test_dead_end_reported() -> None:
    # c jest osiągalna, ale nie prowadzi do FINISH
    assert _r07(_form([("a", "b"), ("a", "c"), ("b", "z")]))


def test_cycle_reported() -> None:
    assert _r07(_form([("a", "b"), ("b", "c"), ("c", "b"), ("c", "z")]))


def test_valid_branching_not_straightened() -> None:
    form = _form(BRANCH)
    result = verify_form(form)
    assert result.form["flow"]["links"] == form["flow"]["links"]
    assert not [i for i in result.fixes if i.code == IssueCode.R07_FLOW]


def test_broken_flow_rebuilt_linearly() -> None:
    result = verify_form(_form([("a", "b"), ("c", "b")]))
    pairs = [(link["source"], link["target"]) for link in result.form["flow"]["links"]]
    assert pairs == LINEAR
