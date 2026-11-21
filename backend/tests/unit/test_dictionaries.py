from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.text import to_tech_name
from app.models.form import Field, FieldType, Option, Question, State, Validator
from app.pipeline.build.dictionaries import (
    bind_dictionary,
    dictionary_violations,
    is_phone_field,
    load_catalog,
    match_dictionary,
    phone_prefix_field,
    propose_dictionaries,
)


def _field(title: str, type_: FieldType = FieldType.SELECT, **kwargs: Any) -> Field:
    return Field(id="id-1", type=type_, tech_name=to_tech_name(title), title=title, **kwargs)


def _options(*names: str) -> list[Option]:
    return [Option(id=n, name=n, tech_name=to_tech_name(n)) for n in names]


def test_catalog_has_dictionaries_from_requirements() -> None:
    names = {d.name for d in load_catalog().dictionaries}
    assert {
        "Kraje",
        "TERYT_4G_DOWODOWY",
        "WOJEWODZTWO",
        "POWIAT",
        "GMINA",
        "MIEJSCOWOSC",
        "NUMERY_KIERUNKOWE",
    } <= names
    # Wymaganie: wszystkie słowniki z katalogu tylko w liście rozwijanej.
    assert all(d.field_types == (FieldType.SELECT,) for d in load_catalog().dictionaries)


def test_proposal_items_get_tech_names() -> None:
    proposal = next(p for p in load_catalog().proposals if p.name == "RODZAJE_PODATKOW_LOKALNYCH")
    assert proposal.status == "PROPOSED"
    assert proposal.items[0].tech_name == "podatek_od_nieruchomosci"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Kraj", "Kraje"),
        ("Kraj urodzenia:", "Kraje"),
        ("Obywatelstwo *", "Kraje"),
        ("Państwo zamieszkania", "Kraje"),
        ("Województwo", "WOJEWODZTWO"),
        ("Powiat", "POWIAT"),
        ("Gmina (opcjonalnie)", "GMINA"),
        ("Miejscowość", "MIEJSCOWOSC"),
        ("Numer kierunkowy", "NUMERY_KIERUNKOWE"),
        ("Miejscowość i data", None),
        ("Kraj docelowy wysyłki towaru", None),
        ("Imię", None),
    ],
)
def test_match_dictionary_by_whole_label(label: str, expected: str | None) -> None:
    entry = match_dictionary(label)
    assert (entry.name if entry else None) == expected


def test_bind_select_sets_dictionary_and_clears_options() -> None:
    field = _field("Kraj", options=_options("Polska", "Niemcy"), validation=[Validator.REQUIRED])
    bound, warnings = bind_dictionary(field)
    assert warnings == []
    assert bound.dictionary_name == "Kraje"
    assert bound.options == []
    assert bound.search_enabled is True
    assert bound.default_value == ["Polska"]
    assert bound.validation == [Validator.REQUIRED]
    assert bound.multi_level_tree is None


def test_bind_keeps_existing_default_value() -> None:
    bound, _ = bind_dictionary(_field("Kraj", default_value=["Niemcy"]))
    assert bound.default_value == ["Niemcy"]


def test_bind_text_field_converts_to_select_with_warning() -> None:
    bound, warnings = bind_dictionary(_field("Gmina", FieldType.TEXT_FIELD), path="tabs[1]")
    assert bound.type is FieldType.SELECT
    assert bound.dictionary_name == "GMINA"
    assert [w.code for w in warnings] == ["W20_DICTIONARY_TYPE_CHANGED"]
    assert warnings[0].path == "tabs[1]"


def test_bind_checkbox_is_not_applied() -> None:
    field = _field("Obywatelstwo", FieldType.CHECKBOX, options=_options("Polskie", "Inne"))
    bound, warnings = bind_dictionary(field)
    assert bound == field
    assert [w.code for w in warnings] == ["W21_DICTIONARY_NOT_APPLIED"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dictionary_name": "TERYT_DOWODOWY"},
        {"read_only": True},
        {"default_value": "MLPZ.country", "default_value_type": "EXTERNAL_SYSTEM"},
    ],
)
def test_bind_skips_fields_with_dictionary_or_initial_data(kwargs: dict[str, Any]) -> None:
    field = _field("Kraj", **kwargs)
    assert bind_dictionary(field) == (field, [])


def test_bind_ignores_unrelated_and_non_choice_fields() -> None:
    for field in (_field("Imię", FieldType.TEXT_FIELD), _field("Kraj", FieldType.NUMBER)):
        assert bind_dictionary(field) == (field, [])


def test_bind_teryt_sets_multi_level_tree() -> None:
    bound, _ = bind_dictionary(_field("TERYT"))
    assert bound.dictionary_name == "TERYT_4G_DOWODOWY"
    assert bound.multi_level_tree is True


def test_bound_field_serializes_like_sample() -> None:
    bound, _ = bind_dictionary(_field("Kraj"))
    data = bound.model_dump(by_alias=True, exclude_none=True, mode="json")
    assert data["dictionaryName"] == "Kraje"
    assert data["options"] == []
    assert data["searchEnabled"] is True
    assert data["defaultValue"] == ["Polska"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Numer telefonu", True),
        ("Telefon kontaktowy:", True),
        ("Numer telefonu (opcjonalnie)", True),
        ("Numer faksu", False),
    ],
)
def test_is_phone_field(label: str, expected: bool) -> None:
    assert is_phone_field(_field(label, FieldType.TEXT_FIELD)) is expected


def test_phone_prefix_field_follows_phone() -> None:
    state = State(type="SHOW", query="true")
    phone = Field(
        id="p",
        type=FieldType.TEXT_FIELD,
        tech_name="numer_telefonu_inna_osoba",
        title="Numer telefonu",
        validation=[Validator.REQUIRED],
        states=[state],
        question_order=3,
    )
    prefix = phone_prefix_field(phone, field_id="x")
    assert prefix.id == "x"
    assert prefix.type is FieldType.SELECT
    assert prefix.tech_name == "numer_kierunkowy_inna_osoba"
    assert prefix.dictionary_name == "NUMERY_KIERUNKOWE"
    assert prefix.default_value == ["+48"]
    assert prefix.validation == [Validator.REQUIRED]
    assert prefix.states == [state]
    assert dictionary_violations(prefix) == []


def test_propose_by_label_for_text_field() -> None:
    proposals = propose_dictionaries([_field("Nazwa podatku", FieldType.TEXT_FIELD)])
    assert [p.name for p in proposals] == ["RODZAJE_PODATKOW_LOKALNYCH"]
    assert proposals[0].used_by == ("nazwa_podatku",)
    assert len(proposals[0].items) == 5


def test_propose_by_options_and_merges_extra_items() -> None:
    field = _field(
        "Wybierz dokument",
        options=_options("Dowód osobisty", "Paszport", "Karta pobytu", "Legitymacja"),
    )
    nested = Field(
        id="s",
        type=FieldType.REPEATING_SECTION,
        tech_name="dokumenty",
        repeating_section_grid=[Question(x=0, y=0, rows=1, cols=3, field=field)],
    )
    other = _field("Rodzaj dokumentu tożsamości", FieldType.TEXT_FIELD)
    proposals = propose_dictionaries([nested, other])
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.name == "RODZAJE_DOKUMENTOW_TOZSAMOSCI"
    assert proposal.used_by == ("wybierz_dokument", "rodzaj_dokumentu_tozsamosci")
    assert proposal.items[-1].name == "Legitymacja"
    assert proposal.items[-1].tech_name == "legitymacja"
    assert len(proposal.items) == 6


def test_propose_skips_fields_with_dictionary_and_weak_overlap() -> None:
    fields = [
        _field("Nazwa podatku", dictionary_name="X"),
        _field("Wybierz", options=_options("Paszport", "Tak", "Nie", "Może")),
    ]
    assert propose_dictionaries(fields) == []


def test_dictionary_violations_r08() -> None:
    bad = _field("Kraj", FieldType.TEXT_FIELD, dictionary_name="Kraje", options=_options("A"))
    errors = dictionary_violations(bad)
    assert len(errors) == 3
    radio = _field("Kraj", FieldType.RADIO, dictionary_name="Kraje")
    assert len(dictionary_violations(radio)) == 1
    unknown = _field("X", FieldType.RADIO, dictionary_name="WLASNY")
    assert dictionary_violations(unknown) == []


def test_get_dictionaries_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/dictionaries")
    assert response.status_code == 200
    body = response.json()
    by_name = {d["name"]: d for d in body}
    assert by_name["Kraje"]["status"] == "PREDEFINED"
    assert by_name["Kraje"]["fieldTypes"] == ["SELECT"]
    assert by_name["TERYT_4G_DOWODOWY"]["multiLevelTree"] is True
    proposed = by_name["RODZAJE_PODATKOW_LOKALNYCH"]
    assert proposed["status"] == "PROPOSED"
    assert proposed["items"][0]["techName"] == "podatek_od_nieruchomosci"
    assert all("labelPatterns" not in d for d in body)
