import pytest

from app.models.form import FieldType, TabType, Validator
from app.pipeline.build.dictionaries import apply_dictionaries
from app.pipeline.build.initial_data import apply_initial_data
from app.pipeline.build.ir import FieldNode, PageNode, SectionNode, Semantic
from app.pipeline.issues import IssueCode


def _node(tech: str = "pole", type_: FieldType = FieldType.TEXT_FIELD, **kw) -> FieldNode:  # type: ignore[no-untyped-def]
    return FieldNode(key=tech, type=type_, title=tech, tech_name=tech, **kw)


def _pages(*nodes: FieldNode) -> list[PageNode]:
    section = SectionNode(
        key="s", type=FieldType.SECTION, title="S", tech_name="s", fields=list(nodes)
    )
    return [PageNode(key="p", title="P", type=TabType.MAIN, sections=[section])]


def test_country_semantic_gets_dictionary() -> None:
    node = _node(semantic=Semantic.COUNTRY, validation=[Validator.PESEL, Validator.REQUIRED])
    apply_dictionaries(_pages(node))
    assert node.dictionary_name == "Kraje"
    assert node.type == FieldType.SELECT
    assert node.validation == [Validator.REQUIRED]
    assert node.options == []
    assert node.search_enabled is True
    assert node.multi_level_tree is None


def test_phone_prefix_semantic_gets_dictionary() -> None:
    node = _node(semantic=Semantic.PHONE_PREFIX)
    apply_dictionaries(_pages(node))
    assert node.dictionary_name == "NUMERY_KIERUNKOWE"
    assert node.type == FieldType.SELECT


@pytest.mark.parametrize(
    ("semantic", "name"),
    [
        (Semantic.VOIVODESHIP, "Województwo"),
        (Semantic.COUNTY, "Powiat"),
        (Semantic.COMMUNE, "Gmina"),
    ],
)
def test_address_unit_semantic_gets_dictionary(semantic: Semantic, name: str) -> None:
    node = _node(semantic=semantic, validation=[Validator.REQUIRED])
    apply_dictionaries(_pages(node))
    assert node.dictionary_name == name
    assert node.type == FieldType.SELECT
    assert node.validation == [Validator.REQUIRED]
    assert node.search_enabled is True


def test_no_semantic_no_dictionary() -> None:
    node = _node("wojewodztwo")
    apply_dictionaries(_pages(node))
    assert node.dictionary_name is None
    assert node.type == FieldType.TEXT_FIELD


def test_ignored_types_untouched() -> None:
    node = _node(type_=FieldType.TEXT_BLOCK, semantic=Semantic.COUNTRY)
    apply_dictionaries(_pages(node))
    assert node.dictionary_name is None


@pytest.mark.parametrize("type_", [FieldType.RADIO, FieldType.SELECT, FieldType.CHECKBOX])
def test_choice_with_own_options_keeps_them(type_: FieldType) -> None:
    node = _node(type_=type_, semantic=Semantic.COUNTRY, options=["Polska", "Niemcy"])
    apply_dictionaries(_pages(node))
    assert node.dictionary_name is None
    assert node.type is type_
    assert node.options == ["Polska", "Niemcy"]


def test_existing_dictionary_untouched() -> None:
    node = _node(semantic=Semantic.COUNTRY, dictionary_name="Inny")
    apply_dictionaries(_pages(node))
    assert node.dictionary_name == "Inny"


def test_editable_mlpz_attribute() -> None:
    node = _node(initial_data="MLPZ.email")
    apply_initial_data(_pages(node))
    assert node.read_only is False
    assert node.default_value == "MLPZ.email"


def test_unknown_ref_skipped() -> None:
    node = _node("moje", initial_data="MLPZ.nope")
    issues = apply_initial_data(_pages(node))
    assert [i.code for i in issues] == [IssueCode.W09_INITIAL_DATA_SKIPPED]
    assert "moje" in issues[0].message
    assert node.default_value is None
    assert node.initial_data is None


def test_dictionary_field_skipped() -> None:
    node = _node(initial_data="MLPZ.email", dictionary_name="Kraje")
    issues = apply_initial_data(_pages(node))
    assert [i.code for i in issues] == [IssueCode.W09_INITIAL_DATA_SKIPPED]
    assert node.initial_data is None
    assert node.default_value is None


def test_semantic_alone_gives_no_initial_data() -> None:
    node = _node(semantic=Semantic.PESEL)
    assert apply_initial_data(_pages(node)) == []
    assert node.default_value is None


def test_initial_data_type_change_filters_validators() -> None:
    node = _node(initial_data="PESEL.birthDate")
    node.validation = [Validator.REQUIRED, Validator.PESEL]
    node.options = ["x"]
    assert apply_initial_data(_pages(node)) == []
    assert node.type == FieldType.DATEPICKER
    assert node.read_only is True
    assert node.default_value == "PESEL.birthDate"
    assert node.default_value_type == "EXTERNAL_SYSTEM"
    assert node.validation == [Validator.REQUIRED]
    assert node.options == []


def test_info_field_untouched_by_initial_data() -> None:
    node = _node(type_=FieldType.INFO_SECTION, initial_data="PESEL.sex")
    assert apply_initial_data(_pages(node)) == []
    assert node.type is FieldType.INFO_SECTION
    assert node.default_value is None
