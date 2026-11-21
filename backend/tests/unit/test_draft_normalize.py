import copy
from pathlib import Path
from typing import Any

from app.models.document import DocumentModel
from app.models.draft import DraftField, FormDraft
from app.pipeline.draft_normalize import matches_text, normalize_draft
from tests.unit.test_draft import _draft

DOC = DocumentModel.model_validate_json(
    (Path(__file__).parent.parent / "fixtures" / "documents" / "wniosek1.json").read_text(
        encoding="utf-8"
    )
)


def _make(mutate: Any = None) -> FormDraft:
    d = copy.deepcopy(_draft())
    # Pola f5/f6 (pytanie o budowę) nie występują w blankiecie - tu ich nie chcemy.
    d["subject_pages"][0]["sections"][0]["fields"] = d["subject_pages"][0]["sections"][0]["fields"][
        :4
    ]
    if mutate:
        mutate(d)
    return FormDraft.model_validate(d)


def _fields(d: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = d["subject_pages"][0]["sections"][0]["fields"]
    return fields


def _field(draft: FormDraft, fid: str) -> DraftField:
    return next(f for _, f in draft.iter_fields() if f.id == fid)


def _codes(warnings: list[Any]) -> list[str]:
    return [w.code for w in warnings]


def _doc_with(text: str) -> DocumentModel:
    return DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [{"number": 1, "blocks": [{"id": "b1", "kind": "paragraph", "text": text}]}],
        }
    )


def test_valid_draft_unchanged() -> None:
    draft = _make()
    out, warnings = normalize_draft(draft, DOC)
    assert out == draft and warnings == []


def test_condition_on_downgraded_choice_is_dropped() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {"id": "f5", "label": "Obręb", "kind": "single_choice", "required": True,
             "options": ["Tak"]}
        )  # fmt: skip
        _fields(d)[3]["visible_when"] = [{"field_id": "f5", "op": "equals", "value": "Tak"}]

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _field(out, "f5").kind == "short_text" and _field(out, "f5").options == []
    assert _field(out, "f4").visible_when == []
    assert set(_codes(warnings)) == {"W15_CHOICE_WITHOUT_OPTIONS"}


def test_single_checkbox_kept() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[3].update(kind="multi_choice", options=["Obręb"])

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _field(out, "f4").kind == "multi_choice" and warnings == []


def test_statement_with_fill_dots_removed() -> None:
    stmt = "Budynek zlokalizowany w miejscowości……………….……………… przy ulicy1)……………….…………………"
    out, warnings = normalize_draft(_make(lambda d: d.update(statements=[stmt])), DOC)
    assert out.statements == [] and _codes(warnings) == ["W17_STATEMENT_REMOVED"]


def test_statement_not_in_document_removed() -> None:
    stmt = "Oświadczam, że dane są prawdziwe"
    out, warnings = normalize_draft(_make(lambda d: d.update(statements=[stmt])), DOC)
    assert out.statements == [] and _codes(warnings) == ["W17_STATEMENT_REMOVED"]


def test_statement_from_document_kept() -> None:
    stmt = "Oświadczam, że jestem właścicielem działki."
    doc = _doc_with(
        "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb. Oświadczam, że "
        "jestem właścicielem"
        " działki."
    )
    out, warnings = normalize_draft(_make(lambda d: d.update(statements=[stmt])), doc)
    assert out.statements == [stmt] and warnings == []


def _title(value: str) -> tuple[str, list[str]]:
    out, warnings = normalize_draft(_make(lambda d: d.update(title=value)), DOC)
    return out.title, _codes(warnings)


def test_uppercase_title_normalized() -> None:
    assert _title("WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO") == (
        "Wniosek o ustalenie numeru porządkowego",
        ["W16_TITLE_CASE_NORMALIZED"],
    )
    assert _title("WNIOSEK O NADANIE NUMERU NIP")[0] == "Wniosek o nadanie numeru NIP"
    assert _title("Wniosek o wydanie zaświadczenia") == ("Wniosek o wydanie zaświadczenia", [])


def test_labels_matched_against_document() -> None:
    _, warnings = normalize_draft(_make(), DOC)
    assert warnings == []

    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[3]["label"] = "Powierzchnia działki"

    _, warnings = normalize_draft(_make(mutate), DOC)
    assert _codes(warnings) == ["W13_FIELD_NOT_IN_DOCUMENT"]
    assert warnings[0].path == "subject_pages[0].sections[0].fields[3]"


def test_page_without_sections_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"].append({"title": "Pusta", "sections": []})

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert [p.title for p in out.subject_pages] == ["Informacje o budynku"]
    assert _codes(warnings) == ["W18_EMPTY_CONTAINER_REMOVED"]


def test_matches_text() -> None:
    assert matches_text("Obręb", "nr działki [POLE] w obrębie [POLE]", 0.6)
    assert matches_text("Numer ewidencyjny działki", "nr ewidencyjny działki [POLE]", 0.6)
    assert not matches_text("Powierzchnia działki", "nr ewidencyjny działki [POLE]", 0.6)


def test_authority_not_in_document_warned() -> None:
    out, warnings = normalize_draft(
        _make(lambda d: d.update(authority_name="Wójt Gminy Elusing")), DOC
    )
    assert _codes(warnings) == ["W19_AUTHORITY_NOT_IN_DOCUMENT"]
    assert out.authority_name == "Wójt Gminy Elusing"


def test_inflected_authority_accepted() -> None:
    doc = _doc_with("Miejscowość Ulica Numer ewidencyjny działki Obręb. Do Urzędu Gminy Elbląg")
    _, warnings = normalize_draft(
        _make(lambda d: d.update(authority_name="Urząd Gminy Elbląg")), doc
    )
    assert warnings == []
