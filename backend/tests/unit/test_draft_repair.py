import copy
from typing import Any

from app.models.draft import FormDraft, LlmDraft
from app.pipeline.draft_repair import repair_draft
from tests.unit.test_draft import _draft, _fields


def _repair(mutate: Any = None) -> tuple[Any, list[str], list[Any]]:
    d = copy.deepcopy(_draft())
    if mutate:
        mutate(d)
    draft, warnings = repair_draft(LlmDraft.model_validate(d))
    return draft, [w.code for w in warnings], warnings


def _cond(d: dict[str, Any]) -> dict[str, Any]:
    cond: dict[str, Any] = _fields(d)[5]["visible_when"][0]
    return cond


def test_valid_draft_unchanged() -> None:
    draft, codes, _ = _repair()
    assert codes == [] and draft == FormDraft.model_validate(_draft())


def test_condition_on_text_field_removed() -> None:
    draft, codes, warnings = _repair(lambda d: _cond(d).update(field_id="f1"))
    assert codes == ["W21_CONDITION_REMOVED"]
    assert "Miejscowość" in warnings[0].message and "nie jest polem wyboru" in warnings[0].message
    assert warnings[0].path == "subject_pages[0].sections[0].fields[5]"
    assert all(not f.visible_when for _, f in draft.iter_fields())


def test_condition_on_missing_or_self_removed() -> None:
    _, codes, warnings = _repair(lambda d: _cond(d).update(field_id="f9"))
    assert codes == ["W21_CONDITION_REMOVED"] and "f9" in warnings[0].message
    _, codes, warnings = _repair(lambda d: _cond(d).update(field_id="f6"))
    assert codes == ["W21_CONDITION_REMOVED"] and "siebie" in warnings[0].message


def test_condition_value_case_fixed_or_removed() -> None:
    draft, codes, _ = _repair(lambda d: _cond(d).update(value=" tak"))
    assert codes == [] and list(draft.iter_fields())[5][1].visible_when[0].value == "Tak"
    _, codes, _ = _repair(lambda d: _cond(d).update(value="Może"))
    assert codes == ["W21_CONDITION_REMOVED"]


def test_duplicate_conditions_collapsed() -> None:
    draft, codes, _ = _repair(lambda d: _fields(d)[5]["visible_when"].append(dict(_cond(d))))
    assert codes == [] and len(list(draft.iter_fields())[5][1].visible_when) == 1


def test_duplicate_and_blank_ids_renumbered() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[1]["id"] = "f1"
        _fields(d)[2]["id"] = " "

    draft, codes, _ = _repair(mutate)
    assert codes == ["W22_FIELD_ID_RENUMBERED"] * 2
    assert [f.id for _, f in draft.iter_fields()] == ["f1", "f7", "f8", "f4", "f5", "f6"]


def test_condition_to_duplicated_id_points_to_first() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[0].update(id="f5")

    draft, codes, _ = _repair(mutate)
    assert codes == ["W22_FIELD_ID_RENUMBERED", "W21_CONDITION_REMOVED"]
    assert [f.id for _, f in draft.iter_fields()][:5] == ["f5", "f2", "f3", "f4", "f7"]


def test_empty_sections_and_pages_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"].append({"title": "Pusta", "sections": [{"title": "S", "fields": []}]})

    draft, codes, warnings = _repair(mutate)
    assert codes == ["W18_EMPTY_CONTAINER_REMOVED"] * 2 and len(draft.subject_pages) == 1
    assert warnings[1].message == "Usunięto pustą stronę „Pusta”."


def test_applicant_kinds_deduplicated_or_defaulted() -> None:
    draft, _, _ = _repair(lambda d: d.update(applicant_kinds=["SELF", "SELF"]))
    assert draft.applicant_kinds == ["SELF"]
    draft, _, _ = _repair(lambda d: d.update(applicant_kinds=[]))
    assert draft.applicant_kinds == ["SELF", "OTHER_PERSON"]


def test_statements_from_model_ignored() -> None:
    draft, _, _ = _repair(lambda d: d.update(statements=["Oświadczam, że wymyśliłem."]))
    assert draft.statements == []
