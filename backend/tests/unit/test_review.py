"""Mapa pochodzenia pól i lista „do sprawdzenia” w raporcie konwersji."""

from pathlib import Path
from typing import Any

from app.models.document import BBox, Block, DocumentModel, Page, SourceInfo
from app.models.draft import DraftField, DraftPage, DraftSection, FormDraft
from app.models.warning import ConversionWarning
from app.pipeline.build import BuildOptions, build_fallback, build_form
from app.pipeline.draft_normalize import label_variants, normalize_draft
from app.pipeline.review import build_review
from app.pipeline.rule_draft import rule_draft

DOCUMENTS = Path(__file__).parents[1] / "fixtures" / "documents"
OPTIONS = BuildOptions(rodo_clause_url="https://bip.example/rodo")


def _doc(*blocks: Block, width: float | None = 600, height: float | None = 800) -> DocumentModel:
    return DocumentModel(
        source=SourceInfo(method="ocr", pages=1),
        pages=[Page(number=1, blocks=list(blocks), width=width, height=height)],
    )


def _block(n: int, text: str, *, confidence: float | None = None, y: float = 0) -> Block:
    return Block(
        id=f"b{n}",
        kind="label",
        text=text,
        bbox=BBox(x0=60, y0=y, x1=360, y1=y + 40),
        ocr_confidence=confidence,
    )


def _draft(*fields: DraftField) -> FormDraft:
    return FormDraft(
        title="Wniosek o zaświadczenie",
        authority_kind="URZAD",
        authority_name="Urząd Miasta",
        applicant_kinds=["SELF"],
        subject_pages=[
            DraftPage(
                title="Sprawa",
                sections=[DraftSection(title="Dane sprawy", repeating=False, fields=list(fields))],
            )
        ],
    )


def _field(fid: str, label: str, kind: str = "short_text", **extra: Any) -> DraftField:
    return DraftField(id=fid, label=label, kind=kind, required=False, **extra)  # type: ignore[arg-type]


def _review(
    doc: DocumentModel, draft: FormDraft, warnings: list[ConversionWarning] | None = None
) -> dict[str, Any]:
    built = build_form(draft, OPTIONS)
    return build_review(
        doc,
        draft,
        built.form.to_import_json(),
        built.field_keys,
        [*built.warnings, *(warnings or [])],
    )


def _by_title(review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["title"]: f for f in review["fields"]}


def test_field_points_to_its_block_with_relative_box() -> None:
    doc = _doc(_block(1, "Wniosek"), _block(2, "Cel wydania zaświadczenia: ........", y=200))
    entry = _by_title(_review(doc, _draft(_field("f1", "Cel wydania zaświadczenia"))))[
        "Cel wydania zaświadczenia"
    ]
    assert entry["origin"] == "document"
    assert entry["level"] == "high"
    assert entry["source"] == {
        "page": 1,
        "blockId": "b2",
        "text": "Cel wydania zaświadczenia: …",
        "box": {"x": 0.1, "y": 0.25, "width": 0.5, "height": 0.05},
        "pageAspect": 0.75,
    }


def test_box_is_omitted_without_page_size() -> None:
    doc = _doc(_block(1, "Cel wydania zaświadczenia"), width=None, height=None)
    entry = _by_title(_review(doc, _draft(_field("f1", "Cel wydania zaświadczenia"))))[
        "Cel wydania zaświadczenia"
    ]
    assert "box" not in entry["source"]


def test_template_fields_are_not_reviewed() -> None:
    doc = _doc(_block(1, "Cel wydania zaświadczenia"))
    review = _review(doc, _draft(_field("f1", "Cel wydania zaświadczenia")))
    templates = [f for f in review["fields"] if f["origin"] == "template"]
    assert templates
    assert all(f["level"] == "high" and "source" not in f for f in templates)
    assert review["confidence"]["fieldsFromDocument"] == 1
    assert review["review"] == []


def test_invented_field_goes_to_review() -> None:
    doc = _doc(_block(1, "Cel wydania zaświadczenia"))
    review = _review(
        doc, _draft(_field("f1", "Cel wydania zaświadczenia"), _field("f2", "Numer paszportu"))
    )
    entry = _by_title(review)["Numer paszportu"]
    assert entry["level"] == "low"
    assert "source" not in entry
    assert [r["code"] for r in entry["reasons"]] == ["LABEL_NOT_IN_DOCUMENT"]
    assert [(i["kind"], i["title"]) for i in review["review"]] == [("field", "Numer paszportu")]
    assert review["confidence"]["toReview"] == 1


def test_low_ocr_confidence_lowers_the_field() -> None:
    doc = _doc(_block(1, "Cel wydania zaświadczenia", confidence=0.4))
    entry = _by_title(_review(doc, _draft(_field("f1", "Cel wydania zaświadczenia"))))[
        "Cel wydania zaświadczenia"
    ]
    assert entry["level"] != "high"
    assert [r["code"] for r in entry["reasons"]] == ["LOW_OCR_CONFIDENCE"]
    assert entry["source"]["ocrConfidence"] == 0.4


def test_options_missing_from_document_are_reported() -> None:
    doc = _doc(_block(1, "Sposób odbioru"), _block(2, "osobiście"))
    field = _field("f1", "Sposób odbioru", "single_choice", options=["osobiście", "gołębiem"])
    entry = _by_title(_review(doc, _draft(field)))["Sposób odbioru"]
    assert [r["code"] for r in entry["reasons"]] == ["OPTIONS_NOT_IN_DOCUMENT"]
    assert "gołębiem" in entry["reasons"][0]["message"]


def test_short_label_does_not_match_inside_other_words() -> None:
    doc = _doc(_block(1, "Kandydata proszę wskazać poniżej"))
    entry = _by_title(_review(doc, _draft(_field("f1", "Data"))))["Data"]
    assert "source" not in entry


def test_normalized_label_is_found_by_its_original_form() -> None:
    assert "miejscowości" in label_variants("Miejscowość")
    assert "nr działki" in label_variants("Numer działki")
    assert label_variants("Ulica") == ["Ulica", "ulicy"]
    doc = _doc(_block(1, "w miejscowości ........ przy ulicy1) ........"))
    fields = _by_title(_review(doc, _draft(_field("f1", "Miejscowość"), _field("f2", "Ulica"))))
    assert fields["Miejscowość"]["source"]["blockId"] == "b1"
    assert fields["Ulica"]["source"]["blockId"] == "b1"


def test_repeated_label_follows_document_order() -> None:
    doc = _doc(_block(1, "Okres od"), _block(2, "Data"), _block(3, "Okres do"), _block(4, "Data"))
    draft = _draft(
        _field("f1", "Okres od"),
        _field("f2", "Data"),
        _field("f3", "Okres do"),
        _field("f4", "Data"),
    )
    sources = [
        f["source"]["blockId"] for f in _review(doc, draft)["fields"] if f["origin"] == "document"
    ]
    assert sources == ["b1", "b2", "b3", "b4"]


def test_form_level_warnings_join_the_list_and_lower_the_score() -> None:
    doc = _doc(_block(1, "Cel wydania zaświadczenia"))
    draft = _draft(_field("f1", "Cel wydania zaświadczenia"))
    clean = _review(doc, draft)
    warned = _review(
        doc,
        draft,
        [
            ConversionWarning(code="W24_RULE_BASED_DRAFT", message="Szkic z reguł."),
            ConversionWarning(code="W16_TITLE_CASE_NORMALIZED", message="Tytuł poprawiono."),
        ],
    )
    assert [(i["kind"], i["code"]) for i in warned["review"]] == [("form", "W24_RULE_BASED_DRAFT")]
    assert warned["confidence"]["score"] < clean["confidence"]["score"]


def test_build_warning_is_attached_to_its_field() -> None:
    doc = _doc(_block(1, "Sposób odbioru"))
    field = _field("f1", "Sposób odbioru", "single_choice", options=[])
    entry = _by_title(_review(doc, _draft(field)))["Sposób odbioru"]
    assert "W07_CHOICE_OPTIONS" in [r["code"] for r in entry["reasons"]]


def test_fallback_form_has_zero_confidence() -> None:
    built = build_fallback(options=OPTIONS)
    review = build_review(
        _doc(_block(1, "Cokolwiek")),
        None,
        built.form.to_import_json(),
        built.field_keys,
        [ConversionWarning(code="W27_FORM_REBUILT", message="Formularz zastępczy.")],
    )
    assert review["confidence"]["score"] == 0.0
    assert review["confidence"]["level"] == "low"
    assert all(f["origin"] == "template" for f in review["fields"])
    assert review["review"][0]["code"] == "W27_FORM_REBUILT"


def test_real_document_through_the_rule_path() -> None:
    doc = DocumentModel.model_validate_json(
        (DOCUMENTS / "numer_porzadkowy.json").read_text(encoding="utf-8")
    )
    draft = rule_draft(doc)
    assert draft is not None
    draft, warnings = normalize_draft(draft, doc)
    review = _review(doc, draft, warnings)
    fields = _by_title(review)
    for title in ("Miejscowość", "Ulica", "Numer ewidencyjny działki", "Obręb"):
        assert fields[title]["level"] == "high", title
        assert fields[title]["source"]["page"] == 1
