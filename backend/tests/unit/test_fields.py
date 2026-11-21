from itertools import count
from typing import Any

import pytest

from app.models.draft import DraftField, DraftSection
from app.models.form import FieldType, Validator
from app.pipeline.build.dictionaries import dictionary_violations
from app.pipeline.build.fields import FieldBuilder


def _builder() -> FieldBuilder:
    ids = count(1)
    return FieldBuilder(id_factory=lambda: f"id-{next(ids)}")


def _draft(label: str, kind: Any = "short_text", **kwargs: Any) -> DraftField:
    return DraftField(id=kwargs.pop("id", "f1"), label=label, kind=kind, **kwargs)


def _one(draft: DraftField, builder: FieldBuilder | None = None) -> Any:
    fields = (builder or _builder()).build_field(draft, "p")
    assert len(fields) == 1
    return fields[0]


@pytest.mark.parametrize(
    ("kind", "options", "expected"),
    [
        ("short_text", [], FieldType.TEXT_FIELD),
        ("long_text", [], FieldType.TEXTAREA),
        ("number", [], FieldType.NUMBER),
        ("date", [], FieldType.DATEPICKER),
        ("file", [], FieldType.FILE_UPLOADER),
        ("multi_choice", ["A", "B"], FieldType.CHECKBOX),
        ("single_choice", ["A", "B", "C", "D", "E"], FieldType.RADIO),
        ("single_choice", ["A", "B", "C", "D", "E", "F"], FieldType.SELECT),
    ],
)
def test_type_mapping(kind: Any, options: list[str], expected: FieldType) -> None:
    field = _one(_draft("Opis sprawy", kind, required=False, options=options))
    assert field.type is expected
    assert field.title == "Opis sprawy"
    assert field.tech_name == "opis_sprawy"


def test_select_with_many_options_has_search() -> None:
    options = [f"Opcja {i}" for i in range(16)]
    field = _one(_draft("Wybierz", "single_choice", required=True, options=options))
    assert field.search_enabled is True
    assert field.options[0].id == field.options[0].name == "Opcja 0"
    assert field.options[0].tech_name == "opcja_0"


def test_options_are_deduplicated() -> None:
    field = _one(_draft("Wybierz", "single_choice", required=True, options=["Tak", "Tak", "Nie"]))
    assert [o.name for o in field.options] == ["Tak", "Nie"]


def test_info_becomes_text_block_without_validation() -> None:
    field = _one(_draft("Opłata wynosi 17 zł <netto>", "info", required=True))
    assert field.type is FieldType.TEXT_BLOCK
    assert field.title == ""
    assert field.validation == []
    assert "Opłata wynosi 17 zł &lt;netto&gt;" in field.description


@pytest.mark.parametrize(
    ("label", "validator"),
    [
        ("Numer PESEL", Validator.PESEL),
        ("NIP", Validator.NIP),
        ("REGON", Validator.REGON),
        ("Kod pocztowy", Validator.ZIP_CODE),
        ("Adres e-mail", Validator.EMAIL),
        ("Adres skrytki ePUAP", Validator.EPUAP),
        ("Adres do e-Doręczeń", Validator.ADE),
        ("Seria i numer dowodu osobistego", Validator.SERIAL_NUMBER_ID_CARD),
    ],
)
def test_format_validators(label: str, validator: Validator) -> None:
    field = _one(_draft(label, required=True))
    assert field.validation == [Validator.REQUIRED, validator]


def test_ambiguous_label_gets_no_format_validator() -> None:
    assert _one(_draft("PESEL lub NIP", required=False)).validation == []


def test_number_with_format_becomes_text_field() -> None:
    field = _one(_draft("Numer PESEL", "number", required=False))
    assert field.type is FieldType.TEXT_FIELD
    assert field.validation == [Validator.PESEL]


def test_format_validator_only_on_text_fields() -> None:
    field = _one(_draft("Data nadania NIP", "date", required=True))
    assert field.validation == [Validator.REQUIRED]


def test_tech_names_are_unique_and_mapped() -> None:
    builder = _builder()
    a = _one(_draft("Kwota", "number", id="f1", required=True), builder)
    b = _one(_draft("Kwota", "number", id="f2", required=True), builder)
    c = _one(_draft("???", id="f3", required=True), builder)
    assert (a.tech_name, b.tech_name, c.tech_name) == ("kwota", "kwota_2", "pole")
    assert builder.draft_ids == {"f1": "kwota", "f2": "kwota_2", "f3": "pole"}


def test_country_text_field_gets_dictionary() -> None:
    builder = _builder()
    field = _one(_draft("Kraj urodzenia", required=True), builder)
    assert field.type is FieldType.SELECT
    assert field.dictionary_name == "Kraje"
    assert field.options == []
    assert field.default_value == ["Polska"]
    assert field.validation == [Validator.REQUIRED]
    assert dictionary_violations(field) == []
    assert [w.code for w in builder.warnings] == ["W20_DICTIONARY_TYPE_CHANGED"]


def test_small_choice_for_voivodeship_uses_dictionary_select() -> None:
    field = _one(_draft("Województwo", "single_choice", required=True, options=["A", "B"]))
    assert field.type is FieldType.SELECT
    assert field.dictionary_name == "WOJEWODZTWO"
    assert field.options == []


def test_phone_gets_prefix_field_before_it() -> None:
    builder = _builder()
    prefix, phone = builder.build_field(_draft("Numer telefonu", required=False), "p")
    assert prefix.dictionary_name == "NUMERY_KIERUNKOWE"
    assert prefix.tech_name == "numer_kierunkowy"
    assert prefix.default_value == ["+48"]
    assert prefix.validation == []
    assert phone.type is FieldType.TEXT_FIELD
    assert phone.tech_name == "numer_telefonu"
    assert prefix.id != phone.id
    assert builder.produced == {"f1": ["numer_kierunkowy", "numer_telefonu"]}
    assert builder.draft_ids == {"f1": "numer_telefonu"}


def test_second_phone_prefix_tech_name_is_unique() -> None:
    builder = _builder()
    builder.build_field(_draft("Numer telefonu", id="f1", required=True), "p")
    prefix, phone = builder.build_field(_draft("Numer telefonu", id="f2", required=True), "p")
    assert phone.tech_name == "numer_telefonu_2"
    assert prefix.tech_name == "numer_kierunkowy_2"
    assert prefix.validation == [Validator.REQUIRED]


def test_section_fields_get_question_order() -> None:
    section = DraftSection(
        title="Kontakt",
        repeating=False,
        fields=[
            _draft("Adres e-mail", id="f1", required=False),
            _draft("Numer telefonu", id="f2", required=False),
        ],
    )
    fields = _builder().build_section_fields(section, "subject_pages[0].sections[0]")
    assert [(f.tech_name, f.question_order) for f in fields] == [
        ("adres_e_mail", 0),
        ("numer_kierunkowy", 1),
        ("numer_telefonu", 2),
    ]


def test_long_label_warning() -> None:
    builder = _builder()
    _one(_draft("x" * 81, required=False), builder)
    assert [w.code for w in builder.warnings] == ["W22_LABEL_TOO_LONG"]
    assert builder.warnings[0].path == "p"
