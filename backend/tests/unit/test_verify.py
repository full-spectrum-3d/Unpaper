import copy
import itertools
import json
import re
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.pipeline.issues import IssueCode
from app.pipeline.verify import verify_form

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SAMPLES = sorted((Path(__file__).parents[3] / "wymagania").glob("konfiguracja_form_*.json"))


def _u(n: int) -> str:
    return str(uuid.UUID(int=n))


def _field(ftype: str, tech: str, fid: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": fid,
        "type": ftype,
        "techName": tech,
        "title": tech,
        "description": "",
        "options": [],
        "validation": [],
        "readOnly": False,
        "repeatingSectionGrid": [],
        "states": [],
        "questionOrder": 0,
        "tooltipMessage": "",
        **extra,
    }


def _q(fld: dict[str, Any]) -> dict[str, Any]:
    return {"x": 0, "y": 0, "rows": 1, "cols": 3, "field": fld}


def _section(tech: str, sid: str, *children: dict[str, Any]) -> dict[str, Any]:
    grid = [_q(c) for c in children]
    return _q(_field("SECTION", tech, sid, description="<html></html>", repeatingSectionGrid=grid))


def _form() -> dict[str, Any]:
    return {
        "title": "Wniosek o test",
        "tabs": [
            {
                "id": _u(1),
                "title": "Dane",
                "type": "MAIN",
                "questions": [_section("s1", _u(3), _field("TEXT_FIELD", "f1", _u(4)))],
            },
            {
                "id": _u(2),
                "title": "Koniec",
                "type": "FINISH",
                "questions": [_section("s2", _u(5), _field("TEXT_BLOCK", "tb", _u(6)))],
            },
        ],
        "flow": {"links": [{"id": _u(7), "source": _u(1), "target": _u(2)}]},
    }


def _query(tech: str) -> str:
    path = "tabs['Dane' in title].questions['s1' in field.techName].field.repeatingSectionGrid"
    return f"'x' in {path}['{tech}' in field.techName].field.__userAnswer"


def _codes(issues: list[Any]) -> set[str]:
    return {i.code for i in issues}


def _first_field(form: dict[str, Any]) -> dict[str, Any]:
    return form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]


def test_minimal_valid_form():
    result = verify_form(_form())
    assert result.valid
    assert result.fixes == []


def test_broken_manual_json():
    form = _form()
    page = form["tabs"][0]
    page["questions"] = [
        _q(_field("TEXT_FIELD", "dup", _u(9))),
        _q(_field("TEXT_FIELD", "dup", _u(9))),
    ]
    for q in page["questions"]:
        del q["field"]["validation"]
    form["tabs"].insert(1, {"id": _u(8), "title": "Pusta", "type": "MAIN", "questions": []})
    del form["flow"]

    broken = verify_form(form, autofix=False)
    assert {
        IssueCode.R03_FIELD_OUTSIDE_SECTION,
        IssueCode.R06_REQUIREDNESS,
        IssueCode.R12_DUPLICATE_ID,
        IssueCode.R12_DUPLICATE_TECH_NAME,
        IssueCode.R03_EMPTY_PAGE,
        IssueCode.R07_FLOW,
    } <= _codes(broken.errors)

    ids = (f"id-{n}" for n in itertools.count())
    fixed = verify_form(form, autofix=True, id_factory=lambda: next(ids))
    assert fixed.valid, fixed.errors
    assert verify_form(fixed.form, autofix=False).valid
    assert len(fixed.form["tabs"]) == 2
    wrapper = fixed.form["tabs"][0]["questions"][0]["field"]
    assert wrapper["type"] == "SECTION"
    assert wrapper["techName"] == "dup_sekcja"
    assert wrapper["repeatingSectionGrid"][0]["field"]["techName"] == "dup"
    assert (
        fixed.form["tabs"][0]["questions"][1]["field"]["repeatingSectionGrid"][0]["field"][
            "techName"
        ]
        == "dup_2"
    )


def test_nested_section_is_flattened():
    form = _form()
    inner = _section("inner", _u(10), _field("TEXT_FIELD", "deep", _u(11)))
    form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"].append(inner)
    assert IssueCode.R04_NESTED_SECTION in _codes(verify_form(form, autofix=False).errors)
    fixed = verify_form(form)
    assert fixed.valid
    names = [
        c["field"]["techName"]
        for c in fixed.form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    ]
    assert names == ["f1", "deep"]


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.stem)
def test_reference_samples_are_repairable(sample: Path):
    data = json.loads(sample.read_text(encoding="utf-8"))
    before = copy.deepcopy(data)
    result = verify_form(data, autofix=True)
    assert result.valid, result.errors
    assert data == before
    if "Nieruchomosci" in sample.stem:
        assert IssueCode.R06_REQUIREDNESS in _codes(result.fixes)


def _keys(node: Any) -> set[str]:
    if isinstance(node, list):
        return set().union(*map(_keys, node)) if node else set()
    if isinstance(node, dict):
        return set(node).union(*map(_keys, node.values()))
    return set()


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.stem)
def test_reference_samples_are_converted_to_document_format(sample: Path):
    result = verify_form(json.loads(sample.read_text(encoding="utf-8")), autofix=True)
    assert result.valid, result.errors
    legacy = {"repetingSectionGrid", "searchEnabled", "multiLevelTree", "minItemRows"}
    assert not legacy & _keys(result.form)
    assert any("Dostosowano klucze" in f.message for f in result.fixes)


def test_document_typo_grid_key_is_renamed():
    form = _form()
    section = form["tabs"][0]["questions"][0]["field"]
    section["repetingSectionGrid"] = section.pop("repeatingSectionGrid")
    for q in section["repetingSectionGrid"]:
        for state in q["field"]["states"]:
            state["query"] = state["query"].replace("repeatingSectionGrid", "repetingSectionGrid")
    result = verify_form(form, autofix=True)
    assert result.valid, result.errors
    fixed = result.form["tabs"][0]["questions"][0]["field"]
    assert "repetingSectionGrid" not in fixed
    assert fixed["repeatingSectionGrid"]
    assert "repetingSectionGrid" not in json.dumps(result.form)
    assert not verify_form(form, autofix=False).valid


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.stem)
def test_legacy_keys_are_errors_without_autofix(sample: Path):
    result = verify_form(json.loads(sample.read_text(encoding="utf-8")), autofix=False)
    assert any("Klucz spoza dokumentu importu" in e.message for e in result.errors)


def test_state_with_unknown_tech_name_removed():
    form = _form()
    query = _query("nie_ma")
    _first_field(form)["states"] = [{"type": "SHOW", "query": query}]
    assert IssueCode.R11_STATE in _codes(verify_form(form, autofix=False).errors)
    result = verify_form(form)
    assert IssueCode.W06_STATE_REMOVED in _codes(result.warnings)
    assert _first_field(result.form)["states"] == []
    assert result.valid


def test_valid_state_is_kept():
    form = _form()
    query = _query("f1")
    form["tabs"][1]["questions"][0]["field"]["states"] = [{"type": "SHOW", "query": query}]
    result = verify_form(form)
    assert result.valid
    assert result.fixes == []


def test_disallowed_validator_removed():
    form = _form()
    _first_field(form).update(type="NUMBER", validation=["REQUIRED", "PESEL"])
    assert IssueCode.R15_VALIDATOR in _codes(verify_form(form, autofix=False).errors)
    assert _first_field(verify_form(form).form)["validation"] == ["REQUIRED"]


def test_finish_input_is_error():
    form = _form()
    form["tabs"][1]["questions"][0]["field"]["repeatingSectionGrid"].append(
        _q(_field("TEXT_FIELD", "wpis", _u(12)))
    )
    for autofix in (False, True):
        assert IssueCode.R05_FINISH_INPUT in _codes(verify_form(form, autofix=autofix).errors)


def test_initial_data_rules():
    def run(ref: str, read_only: bool) -> set[str]:
        form = _form()
        _first_field(form).update(
            defaultValueType="EXTERNAL_SYSTEM", defaultValue=ref, readOnly=read_only
        )
        return _codes(verify_form(form, autofix=False).errors)

    assert IssueCode.R10_INITIAL_DATA in run("MLPZ.name", False)
    assert IssueCode.R10_INITIAL_DATA not in run("MLPZ.name", True)
    assert IssueCode.R10_INITIAL_DATA not in run("MLPZ.email", False)
    assert IssueCode.R10_INITIAL_DATA in run("MLPZ.nope", True)


def test_choice_dictionary_and_options_rules():
    form = _form()
    _first_field(form).update(type="SELECT", options=[{"id": "a", "name": "a", "techName": "a"}])
    assert IssueCode.R09_OPTIONS in _codes(verify_form(form, autofix=False).errors)
    _first_field(form).update(dictionaryName="KRAJE")
    assert IssueCode.R08_DICTIONARY in _codes(verify_form(form, autofix=False).errors)
    fixed = verify_form(form)
    assert fixed.valid
    assert _first_field(fixed.form)["options"] == []
    _first_field(form).update(type="TEXT_FIELD")
    assert "dictionaryName" not in _first_field(verify_form(form).form)


def test_consent_and_info_section_rules():
    form = _form()
    _first_field(form).update(
        type="CONSENT_SECTION", consentSectionConfig={"consents": [], "files": []}
    )
    form["tabs"][1]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]["type"] = (
        "INFO_SECTION"
    )
    codes = _codes(verify_form(form).errors)
    assert {IssueCode.R13_CONSENT, IssueCode.R14_INFO_SECTION} <= codes


def test_tabs_rules():
    form = _form()
    form["tabs"][1]["type"] = "MAIN"
    assert IssueCode.R02_TABS in _codes(verify_form(form).errors)
    form = _form()
    del form["tabs"][1]
    assert IssueCode.R02_TABS in _codes(verify_form(form).errors)


def test_garbage_input():
    result = verify_form({"tabs": 5})
    assert IssueCode.SCHEMA in _codes(result.errors)
    assert not result.valid
    assert IssueCode.SCHEMA in _codes(
        verify_form({"tabs": [1, {"questions": [{"field": 3}]}]}).errors
    )
    assert not verify_form({"tabs": [{"questions": "x"}], "flow": []}, autofix=False).valid


def test_unknown_field_type_is_schema_error():
    form = _form()
    _first_field(form)["type"] = "MAGIC"
    errors = verify_form(form).errors
    assert any(i.code == IssueCode.SCHEMA and "Nieznany typ pola" in i.message for i in errors)


def test_title_prefix_is_warning():
    form = _form()
    form["title"] = "Karta"
    result = verify_form(form)
    assert IssueCode.W05_TITLE_PREFIX in _codes(result.warnings)
    assert result.valid
    form["title"] = ""
    assert IssueCode.R01_TITLE in _codes(verify_form(form).errors)


@pytest.mark.parametrize("blank", ["", None])
def test_blank_dictionary_name_keeps_options_and_is_dropped(blank: str | None):
    form = _form()
    _first_field(form).update(
        type="SELECT",
        dictionaryName=blank,
        options=[
            {"id": "a", "name": "a", "techName": "a"},
            {"id": "b", "name": "b", "techName": "b"},
        ],
    )
    if blank == "":  # None łamie schemat, więc tylko autofix
        assert verify_form(copy.deepcopy(form), autofix=False).valid
    fixed = verify_form(form)
    assert fixed.valid
    field = _first_field(fixed.form)
    assert "dictionaryName" not in field
    assert len(field["options"]) == 2
    assert IssueCode.R08_DICTIONARY in {f.code for f in fixed.fixes}


@pytest.mark.parametrize(
    ("tech", "expected"),
    [(None, "sekcja"), ("", "sekcja"), (5, "sekcja"), ("pole", "pole_sekcja")],
)
def test_wrapper_tech_name_never_has_junk_prefix(tech: Any, expected: str):
    form = _form()
    loose = _field("TEXT_FIELD", "x", _u(13), title="")
    loose["techName"] = tech
    form["tabs"][0]["questions"].append(_q(loose))
    fixed = verify_form(form)
    wrapper = fixed.form["tabs"][0]["questions"][-1]["field"]
    assert wrapper["techName"] == expected


# --- C1: strona końcowa tylko z INFO_SECTION (ostrzeżenie) ---


def test_finish_page_non_info_section_is_warning():
    result = verify_form(_form())
    assert result.valid
    warned = [w for w in result.warnings if w.code == IssueCode.W29_FINISH_NOT_INFO]
    assert [w.path for w in warned] == ["tabs[1].questions[0].field.repeatingSectionGrid[0]"]


def test_finish_page_info_section_has_no_warning():
    form = _form()
    finish = form["tabs"][1]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]
    finish.update(type="INFO_SECTION", description="<p>Podgląd</p>")
    result = verify_form(form)
    assert result.valid, result.errors
    assert IssueCode.W29_FINISH_NOT_INFO not in _codes(result.warnings)


def test_finish_input_is_error_not_extra_warning():
    form = _form()
    form["tabs"][1]["questions"][0]["field"]["repeatingSectionGrid"].append(
        _q(_field("TEXT_FIELD", "wpis", _u(12)))
    )
    warned = [w for w in verify_form(form).warnings if w.code == IssueCode.W29_FINISH_NOT_INFO]
    assert len(warned) == 1  # tylko TEXT_BLOCK; pole wejściowe to błąd R05


# --- C3: niepusty tytuł sekcji ---


def _section_field(form: dict[str, Any]) -> dict[str, Any]:
    return form["tabs"][0]["questions"][0]["field"]


@pytest.mark.parametrize("blank", ["", "   ", None, 5])
def test_blank_section_title_is_error_and_fixed_from_first_field(blank: Any):
    form = _form()
    _section_field(form)["title"] = blank
    _first_field(form)["title"] = "Imię"
    assert IssueCode.R16_SECTION_TITLE in _codes(verify_form(form, autofix=False).errors)
    fixed = verify_form(form)
    assert fixed.valid, fixed.errors
    assert _section_field(fixed.form)["title"] == "Imię"
    assert IssueCode.R16_SECTION_TITLE in _codes(fixed.fixes)


def test_blank_section_title_falls_back_to_dane():
    form = _form()
    _section_field(form)["title"] = " "
    _first_field(form)["title"] = ""
    assert _section_field(verify_form(form).form)["title"] == "Dane"
    form = _form()
    _section_field(form).update(title="", repeatingSectionGrid=[])
    assert _section_field(verify_form(form).form)["title"] == "Dane"


def test_blank_repeating_section_title_is_error():
    form = _form()
    _section_field(form).update(type="REPEATING_SECTION", title="")
    assert IssueCode.R16_SECTION_TITLE in _codes(verify_form(form, autofix=False).errors)


def test_non_section_blank_title_is_not_flagged():
    form = _form()
    _first_field(form)["title"] = ""
    assert IssueCode.R16_SECTION_TITLE not in _codes(verify_form(form, autofix=False).errors)


def test_section_title_fix_keeps_states_valid():
    form = _form()
    _section_field(form)["title"] = ""
    form["tabs"][1]["questions"][0]["field"]["states"] = [{"type": "SHOW", "query": _query("f1")}]
    fixed = verify_form(form)
    assert fixed.valid
    assert IssueCode.W06_STATE_REMOVED not in _codes(fixed.warnings)


# --- C4: format UUID ---


def _id_warnings(result: Any) -> list[Any]:
    return [w for w in result.warnings if w.code == IssueCode.W30_ID_FORMAT]


def test_non_uuid_ids_warn_and_are_replaced_consistently():
    form = _form()
    form["tabs"][0]["id"] = "strona-1"
    form["tabs"][1]["id"] = "strona-2"
    form["flow"]["links"][0].update(id="link-1", source="strona-1", target="strona-2")
    _first_field(form)["id"] = "pole-1"
    warned = verify_form(form, autofix=False)
    assert warned.valid
    assert len(_id_warnings(warned)) == 4

    fixed = verify_form(form)
    assert fixed.valid, fixed.errors
    assert not _id_warnings(fixed)
    tab1, tab2 = (t["id"] for t in fixed.form["tabs"])
    link = fixed.form["flow"]["links"][0]
    assert (link["source"], link["target"]) == (tab1, tab2)
    ids = [tab1, tab2, link["id"], _first_field(fixed.form)["id"]]
    assert all(UUID_RE.match(i) for i in ids)
    assert len(set(ids)) == 4
    assert {f.code for f in fixed.fixes} == {IssueCode.W30_ID_FORMAT}


def test_uuid_ids_are_left_alone():
    result = verify_form(_form())
    assert IssueCode.W30_ID_FORMAT not in {f.code for f in result.fixes}
    assert result.form["tabs"][0]["id"] == _u(1)
    assert not _id_warnings(result)
