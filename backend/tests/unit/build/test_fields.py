from typing import Any

import pytest

from app.models.draft import Condition, DraftField, FieldKind
from app.models.form import FieldType, TabType, Validator
from app.pipeline.build.fields import (
    assign_unique_tech_names,
    convert_conditions,
    label_semantic,
    map_draft_field,
    normalize_title,
    slugify,
)
from app.pipeline.build.ir import AllOf, Eq, FieldNode, Not, PageNode, SectionNode, Semantic
from app.pipeline.issues import IssueCode


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Numer PESEL", "numer_pesel"),
        ("Adres e-mail", "adres_e_mail"),
        ("Podatek, którego dotyczy nadpłata", "podatek_ktorego_dotyczy_nadplata"),
        ("Wybierz, co mamy zrobić z nadpłatą", "wybierz_co_mamy_zrobic_z_nadplata"),
        (
            "Urząd, do którego jest składany wniosek",
            "urzad_do_ktorego_jest_skladany_wniosek",
        ),
        ("Źródło łąki – ŻÓŁW", "zrodlo_laki_zolw"),  # noqa: RUF001
        ("!!!", "pole"),
    ],
)
def test_slugify_matches_reference_tech_names(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_max_length() -> None:
    result = slugify("ab " * 50)
    assert len(result) <= 60
    assert not result.endswith("_")


def test_normalize_title() -> None:
    title, issues = normalize_title("  Karta   ")
    assert title == "Karta"
    assert [i.code for i in issues] == [IssueCode.W05_TITLE_PREFIX]

    title, issues = normalize_title("Wniosek " + "x" * 300)
    assert len(title) == 255
    assert [i.code for i in issues] == [IssueCode.W08_TITLE_TRUNCATED]

    title, issues = normalize_title("   ")
    assert title == "Wniosek"
    assert [i.code for i in issues] == [IssueCode.W05_TITLE_PREFIX]


def _field(label: str, kind: FieldKind, **kwargs: Any) -> DraftField:
    kwargs.setdefault("required", False)
    return DraftField(id="f1", label=label, kind=kind, **kwargs)


def _choice(n: int) -> DraftField:
    return _field("Wybór", "single_choice", options=[f"o{i}" for i in range(n)])


def test_choice_mapping() -> None:
    node, _ = map_draft_field(_choice(3), key="k")
    assert node.type is FieldType.RADIO

    node, _ = map_draft_field(_choice(6), key="k")
    assert node.type is FieldType.SELECT
    assert node.search_enabled is None

    node, _ = map_draft_field(_choice(16), key="k")
    assert node.type is FieldType.SELECT
    assert node.search_enabled is True

    node, issues = map_draft_field(_choice(1), key="k")
    assert node.type is FieldType.CHECKBOX
    assert [i.code for i in issues] == [IssueCode.W07_CHOICE_OPTIONS]

    node, issues = map_draft_field(_choice(0), key="k")
    assert node.type is FieldType.TEXT_FIELD
    assert [i.code for i in issues] == [IssueCode.W07_CHOICE_OPTIONS]


def test_validators() -> None:
    field = _field("Kod pocztowy", "short_text", required=True)
    node, _ = map_draft_field(field, key="k")
    assert node.validation == [Validator.REQUIRED, Validator.ZIP_CODE]

    # PESEL ze szkicu jako liczba staje się tekstem, żeby nie stracić walidatora formatu.
    field = _field("Numer PESEL", "number", required=True)
    node, _ = map_draft_field(field, key="k")
    assert node.validation == [Validator.REQUIRED, Validator.PESEL]

    field = _field("Adres e-mail", "short_text")
    node, _ = map_draft_field(field, key="k")
    assert node.validation == [Validator.EMAIL]


def test_info_field_is_text_block() -> None:
    field = _field("Uwaga", "info", required=True)
    node, _ = map_draft_field(field, key="k")
    assert node.type is FieldType.TEXT_BLOCK
    assert node.title == ""
    assert node.description_html.startswith("<p>")
    assert node.validation == []


def test_convert_conditions() -> None:
    a = FieldNode(key="a", type=FieldType.RADIO, title="A", tech_name="a")
    b = FieldNode(key="b", type=FieldType.CHECKBOX, title="B", tech_name="b")
    owner = FieldNode(key="o", type=FieldType.TEXT_FIELD, title="O", tech_name="o")
    by_id = {"f1": a, "f2": b, "f3": owner}

    eq = Condition(field_id="f1", op="equals", value="x")
    neq = Condition(field_id="f2", op="not_equals", value="y")
    assert convert_conditions([eq], by_id, owner) == Eq("a", "x")
    assert convert_conditions([neq], by_id, owner) == Not(Eq("b", "y"))
    assert convert_conditions([eq, neq], by_id, owner) == AllOf((Eq("a", "x"), Not(Eq("b", "y"))))


def test_convert_conditions_unresolved() -> None:
    a = FieldNode(key="a", type=FieldType.RADIO, title="A", tech_name="a")
    text = FieldNode(key="t", type=FieldType.TEXT_FIELD, title="T", tech_name="t")
    by_id = {"f1": a, "f2": text}
    ok = Condition(field_id="f1", op="equals", value="x")

    def convert(*conds: Condition, owner: FieldNode = text) -> object:
        return convert_conditions(list(conds), by_id, owner)

    assert convert(Condition(field_id="nie_ma", op="equals", value="x")) is None
    assert convert(Condition(field_id="f2", op="equals", value="x"), owner=a) is None
    assert convert(Condition(field_id="f1", op="equals", value="x"), owner=a) is None
    # jeden nierozwiązany warunek unieważnia całość (AND)
    assert convert(ok, Condition(field_id="nie_ma", op="equals", value="x")) is None
    assert convert() is None


def test_assign_unique_tech_names() -> None:
    def node(key: str) -> FieldNode:
        return FieldNode(key=key, type=FieldType.TEXT_FIELD, title="Ulica", tech_name="ulica")

    section = SectionNode(
        key="s", type=FieldType.SECTION, title="Ulica", tech_name="ulica", fields=[node("f1")]
    )
    page = PageNode(key="p", title="P", type=TabType.MAIN, sections=[section])
    section.fields.append(node("f2"))
    assign_unique_tech_names([page])
    assert section.tech_name == "ulica"
    assert [f.tech_name for f in section.fields] == ["ulica_2", "ulica_3"]


def test_assign_unique_tech_names_respects_max_length() -> None:
    long_name = "a" * 60

    def node(key: str) -> FieldNode:
        return FieldNode(key=key, type=FieldType.TEXT_FIELD, title="x", tech_name=long_name)

    section = SectionNode(
        key="s", type=FieldType.SECTION, title="S", tech_name="s", fields=[node("1"), node("2")]
    )
    assign_unique_tech_names([PageNode(key="p", title="P", type=TabType.MAIN, sections=[section])])
    assert section.fields[0].tech_name == long_name
    assert section.fields[1].tech_name == "a" * 58 + "_2"


def test_choice_boundaries() -> None:
    node, _ = map_draft_field(_choice(5), key="k")
    assert node.type is FieldType.RADIO
    node, _ = map_draft_field(_choice(15), key="k")
    assert node.type is FieldType.SELECT
    assert node.search_enabled is None


def test_multi_choice_mapping() -> None:
    field = _field("M", "multi_choice", options=["a", "b"])
    node, issues = map_draft_field(field, key="k")
    assert node.type is FieldType.CHECKBOX
    assert node.options == ["a", "b"]
    assert issues == []

    node, issues = map_draft_field(_field("M", "multi_choice"), key="k")
    assert node.type is FieldType.TEXT_FIELD
    assert [i.code for i in issues] == [IssueCode.W07_CHOICE_OPTIONS]


def test_label_too_long_warns() -> None:
    field = _field("x" * 81, "short_text")
    _, issues = map_draft_field(field, key="k")
    assert [i.code for i in issues] == [IssueCode.W02_LABEL_TOO_LONG]


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("short_text", FieldType.TEXT_FIELD),
        ("long_text", FieldType.TEXTAREA),
        ("number", FieldType.NUMBER),
        ("date", FieldType.DATEPICKER),
        ("file", FieldType.FILE_UPLOADER),
    ],
)
def test_simple_kind_mapping(kind: FieldKind, expected: FieldType) -> None:
    node, issues = map_draft_field(_field("Pole", kind), key="k")
    assert node.type is expected
    assert issues == []


def test_plain_field_has_no_description_or_tooltip() -> None:
    node, _ = map_draft_field(_field("Pole", "short_text"), key="k")
    assert node.description_html == ""
    assert node.tooltip == ""
    assert node.tech_name == "pole"
    assert node.semantic is None


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Numer NIP", Validator.NIP),
        ("Numer REGON", Validator.REGON),
        ("Adres skrytki ePUAP", Validator.EPUAP),
        ("Adres do e-doręczeń", Validator.ADE),
        ("Seria i numer dowodu osobistego", Validator.SERIAL_NUMBER_ID_CARD),
        ("Adres poczty elektronicznej", Validator.EMAIL),
    ],
)
def test_label_regex_validators(label: str, expected: Validator) -> None:
    node, _ = map_draft_field(_field(label, "short_text"), key="k")
    assert node.validation == [expected]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Numer PESEL", Semantic.PESEL),
        ("Kraj", Semantic.COUNTRY),
        ("Kraj urodzenia", Semantic.COUNTRY),
        ("Państwo zamieszkania", Semantic.COUNTRY),
        ("Obywatelstwo", Semantic.COUNTRY),
        ("Numer kierunkowy", Semantic.PHONE_PREFIX),
        ("Numer kierunkowy kraju", Semantic.PHONE_PREFIX),
        ("Kod pocztowy", Semantic.ZIP_CODE),
        ("Województwo", Semantic.VOIVODESHIP),
        ("Powiat:", Semantic.COUNTY),
        ("Gmina", Semantic.COMMUNE),
        ("Miejscowość", None),
        ("Miejscowość i data", None),
        ("Powiat grodzki lub ziemski", None),
        ("Ulica", None),
    ],
)
def test_label_semantic(label: str, expected: Semantic | None) -> None:
    assert label_semantic(label) is expected
    node, _ = map_draft_field(_field(label, "short_text"), key="k")
    assert node.semantic is expected


def test_file_field_has_no_semantic() -> None:
    node, _ = map_draft_field(_field("Kraj", "file"), key="k")
    assert node.semantic is None
    assert node.type is FieldType.FILE_UPLOADER


def test_info_label_is_escaped() -> None:
    node, _ = map_draft_field(_field("<b>x</b>", "info"), key="k")
    assert node.description_html == "<p>&lt;b&gt;x&lt;/b&gt;</p>"


def test_duplicate_draft_options_are_deduplicated_with_warning() -> None:
    draft = _field("Czy zgadzasz się", "single_choice", options=["Tak", "Tak", "Nie"])
    node, issues = map_draft_field(draft, key="p1.s1.f1")
    assert node.options == ["Tak", "Nie"]
    assert [i.code for i in issues] == [IssueCode.W07_CHOICE_OPTIONS]


@pytest.mark.parametrize(
    ("label", "kind", "expected"),
    [
        ("Kod pocztowy", "number", FieldType.TEXT_FIELD),
        ("PESEL", "number", FieldType.TEXT_FIELD),
        ("Kwota zapłaty", "short_text", FieldType.NUMBER),
        ("Suma opłat", "short_text", FieldType.NUMBER),
        ("Razem", "short_text", FieldType.NUMBER),
        ("Łączna kwota opłat", "short_text", FieldType.NUMBER),
        ("Należność (zł)", "short_text", FieldType.NUMBER),
        ("Wysokość opłaty w PLN", "short_text", FieldType.NUMBER),
        ("Kwota słownie", "short_text", FieldType.TEXT_FIELD),
        ("Numer rachunku do zwrotu kwoty", "short_text", FieldType.TEXT_FIELD),
        ("Nazwa organu, w którym zapłacono opłatę", "short_text", FieldType.TEXT_FIELD),
        ("Liczba psów", "number", FieldType.NUMBER),
    ],
)
def test_type_follows_label(label: str, kind: FieldKind, expected: FieldType) -> None:
    node, _ = map_draft_field(_field(label, kind), key="k")
    assert node.type is expected


def test_zip_code_typed_as_number_keeps_format_validator() -> None:
    node, _ = map_draft_field(_field("Kod pocztowy", "number", required=True), key="k")
    assert node.validation == [Validator.REQUIRED, Validator.ZIP_CODE]
