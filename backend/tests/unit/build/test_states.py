import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.models.form import FieldType, TabType
from app.pipeline.build.ir import AllOf, AnyOf, Condition, Eq, FieldNode, Not, PageNode, SectionNode
from app.pipeline.build.states import (
    FieldLocation,
    build_states,
    check_condition_query,
    condition_to_jsonata,
    query_compiles,
    query_references,
)
from app.pipeline.issues import IssueCode

REFERENCE = (
    Path(__file__).parents[4]
    / "wymagania"
    / "konfiguracja_form_wniosekOStwierdzenieNadplatyPodatku.json"
)

LOCATIONS = {
    "kto": FieldLocation(
        "Dane", "podmiot_wniosku", "wybierz_w_czyim_imieniu_wnioskujesz", False, "s1"
    ),
    "rola": FieldLocation("Dane", "podmiot_wniosku", "wybierz_jako_kto_wnioskujesz", False, "s1"),
    "kraj": FieldLocation("Dane", "adres_zamieszkania", "kraj", False, "s2"),
    "inna": FieldLocation("Druga", "sekcja", "pole", False, "s3"),
    "rep": FieldLocation("Dane", "powtarzana", "pole_rep", True, "s4"),
}


def locate(ref: str) -> FieldLocation:
    try:
        return LOCATIONS[ref]
    except KeyError:
        raise ValueError(ref) from None


def _find_state(node: Any, tech_name: str) -> str | None:
    if isinstance(node, dict):
        if node.get("techName") == tech_name and node.get("states"):
            return str(node["states"][0]["query"])
        for value in node.values():
            found = _find_state(value, tech_name)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_state(value, tech_name)
            if found:
                return found
    return None


CASES: list[tuple[str, Condition]] = [
    (
        "wybierz_jako_kto_wnioskujesz",
        Eq("kto", "Osoby prawnej lub jednostki organizacyjnej"),
    ),
    ("ulica_zagranica", Not(Eq("kraj", "Polska"))),
    (
        "pelnomocnictwo",
        AnyOf(
            (
                Eq("kto", "Innej osoby"),
                AllOf(
                    (
                        Eq("kto", "Osoby prawnej lub jednostki organizacyjnej"),
                        Eq("rola", "Pełnomocnik"),
                    )
                ),
            )
        ),
    ),
]


@pytest.mark.parametrize(("tech_name", "cond"), CASES)
def test_matches_reference_queries(tech_name: str, cond: Condition) -> None:
    expected = _find_state(json.loads(REFERENCE.read_text(encoding="utf-8")), tech_name)
    assert expected is not None
    query = condition_to_jsonata(cond, locate, context_section_key=None)
    assert "\n" not in query
    assert re.sub(r"\s+", "", query) == re.sub(r"\s+", "", expected)


def test_semantic_check_passes_for_compound() -> None:
    cond = AnyOf((Eq("kto", "A"), AllOf((Eq("inna", "B"), Not(Eq("kraj", "C"))))))
    query = condition_to_jsonata(cond, locate, context_section_key=None)
    assert check_condition_query(query, cond, locate)
    assert not check_condition_query(query, Not(cond), locate)


def test_repeating_section_query() -> None:
    cond = Eq("rep", "x")
    query = condition_to_jsonata(cond, locate, context_section_key="s4")
    assert "$repeatingSectionIndex" in query
    assert "fieldTechName" in query
    assert check_condition_query(query, cond, locate)
    with pytest.raises(ValueError):
        condition_to_jsonata(cond, locate, context_section_key=None)


def test_quotes_in_values_and_titles() -> None:
    loc = FieldLocation("Strona 'X'", "sek", "pole", False, "s")
    cond = Eq("r", "Wniosek „a” \"b\" 'c' \\ d")
    query = condition_to_jsonata(cond, lambda _: loc, context_section_key=None)
    assert query_compiles(query) is None
    assert check_condition_query(query, cond, lambda _: loc)
    assert query_references(query)[0] == {"Strona 'X'"}
    assert query_references(query)[1] == {"sek", "pole"}


def test_query_compiles_reports_error() -> None:
    assert query_compiles("tabs['x' in ") is not None


def _pages() -> list[PageNode]:
    field = FieldNode(key="f1", type=FieldType.TEXT_FIELD, title="F", tech_name="f")
    other = FieldNode(
        key="f2",
        type=FieldType.TEXT_FIELD,
        title="G",
        tech_name="g",
        show_when=Eq("f1", "tak"),
        read_only_when=Eq("nieznany", "x"),
    )
    section = SectionNode(
        key="s", type=FieldType.SECTION, title="S", tech_name="s", fields=[field, other]
    )
    return [PageNode(key="p", title="P", type=TabType.MAIN, sections=[section])]


def test_unknown_ref_removed_with_warning() -> None:
    states, issues = build_states(_pages())
    assert [s["type"] for s in states["f2"]] == ["SHOW"]
    assert len(issues) == 1
    assert issues[0].code == IssueCode.W06_STATE_REMOVED
    assert issues[0].path == "f2"


def test_read_only_state_is_built_from_condition() -> None:
    field = FieldNode(key="f1", type=FieldType.TEXT_FIELD, title="F", tech_name="f")
    locked = FieldNode(
        key="f2",
        type=FieldType.TEXT_FIELD,
        title="G",
        tech_name="g",
        read_only_when=Not(Eq("f1", "tak")),
    )
    section = SectionNode(
        key="s", type=FieldType.SECTION, title="S", tech_name="s", fields=[field, locked]
    )
    pages = [PageNode(key="p", title="P", type=TabType.MAIN, sections=[section])]
    states, issues = build_states(pages)
    assert not issues
    assert [s["type"] for s in states["f2"]] == ["READ_ONLY"]
    assert query_compiles(states["f2"][0]["query"]) is None
