from typing import Any

from fastapi.testclient import TestClient

from app.models.draft import DraftField, DraftPage, DraftSection, FormDraft
from app.models.form import Field, FieldType, Option, Question
from app.pipeline.build import build_form
from app.pipeline.build.fields import slugify
from app.pipeline.build.proposals import (
    load_proposal_catalog,
    propose_dictionaries,
    propose_for_fields,
)


def _field(title: str, type_: FieldType = FieldType.SELECT, **kwargs: Any) -> Field:
    return Field(id="id", type=type_, tech_name=slugify(title), title=title, **kwargs)


def _options(*names: str) -> list[Option]:
    return [Option(id=n, name=n, tech_name=slugify(n)) for n in names]


def test_catalog_items_get_tech_names() -> None:
    taxes = next(t for t in load_proposal_catalog() if t.name == "RODZAJE_PODATKOW_LOKALNYCH")
    assert taxes.items[0].tech_name == "podatek_od_nieruchomosci"
    assert taxes.items[-1].tech_name == "laczne_zobowiazanie_pieniezne"


def test_propose_by_label_for_text_field() -> None:
    proposals = propose_for_fields([_field("Nazwa podatku:", FieldType.TEXT_FIELD)])
    assert [p.name for p in proposals] == ["RODZAJE_PODATKOW_LOKALNYCH"]
    assert proposals[0].used_by == ("nazwa_podatku",)
    assert len(proposals[0].items) == 5


def test_fees_are_a_separate_proposal_from_taxes() -> None:
    proposals = propose_for_fields(
        [
            _field("Nazwa podatku", FieldType.TEXT_FIELD),
            _field("Rodzaj opłaty", FieldType.TEXT_FIELD),
            _field(
                "Czego dotyczy nadpłata",
                options=_options("Opłata targowa", "Opłata skarbowa", "Opłata miejscowa"),
            ),
        ]
    )
    assert [p.name for p in proposals] == [
        "RODZAJE_PODATKOW_LOKALNYCH",
        "RODZAJE_OPLAT_LOKALNYCH",
    ]
    fees = proposals[1]
    assert fees.used_by == ("rodzaj_oplaty", "czego_dotyczy_nadplata")
    assert len(fees.items) == 7
    assert "Opłata skarbowa" not in {i.name for i in proposals[0].items}


def test_propose_by_options_in_repeating_section_and_merges_extra_items() -> None:
    choice = _field(
        "Wybierz dokument",
        options=_options("Dowód osobisty", "Paszport", "Karta pobytu", "Legitymacja"),
    )
    section = Field(
        id="s",
        type=FieldType.REPEATING_SECTION,
        tech_name="dokumenty",
        repeating_section_grid=[Question(x=0, y=0, rows=1, cols=3, field=choice)],
    )
    text = _field("Rodzaj dokumentu tożsamości", FieldType.TEXT_FIELD)
    proposals = propose_for_fields([section, text])
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.name == "RODZAJE_DOKUMENTOW_TOZSAMOSCI"
    assert proposal.used_by == ("wybierz_dokument", "rodzaj_dokumentu_tozsamosci")
    assert proposal.items[-1].name == "Legitymacja"
    assert proposal.items[-1].code == "LEGITYMACJA"
    assert len(proposal.items) == 6


def test_skips_fields_with_dictionary_weak_overlap_and_other_types() -> None:
    fields = [
        _field("Nazwa podatku", dictionary_name="X"),
        _field("Nazwa podatku", FieldType.NUMBER),
        _field("Wybierz", options=_options("Paszport", "Tak", "Nie", "Może")),
    ]
    assert propose_for_fields(fields) == []


def test_propose_from_built_form() -> None:
    draft = FormDraft(
        title="Wniosek o stwierdzenie nadpłaty podatku",
        authority_kind="ORGAN",
        authority_name="Burmistrz Miasta",
        applicant_kinds=["SELF"],
        subject_pages=[
            DraftPage(
                title="Informacje o nadpłacie",
                sections=[
                    DraftSection(
                        title="Nadpłata",
                        repeating=False,
                        fields=[
                            DraftField(
                                id="f1", label="Nazwa podatku", kind="short_text", required=True
                            )
                        ],
                    )
                ],
            )
        ],
    )
    proposals = propose_dictionaries(build_form(draft).form)
    assert [p.name for p in proposals] == ["RODZAJE_PODATKOW_LOKALNYCH"]
    assert proposals[0].used_by == ("nazwa_podatku",)


def test_get_dictionaries_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/dictionaries")
    assert response.status_code == 200
    by_name = {d["name"]: d for d in response.json()}
    assert by_name["Kraje"]["status"] == "PREDEFINED"
    assert by_name["Kraje"]["fieldTypes"] == ["SELECT"]
    assert by_name["TERYT_4G_DOWODOWY"]["multiLevelTree"] is True
    assert by_name["NUMERY_KIERUNKOWE"]["status"] == "PREDEFINED"
    proposed = by_name["RODZAJE_PODATKOW_LOKALNYCH"]
    assert proposed["status"] == "PROPOSED"
    assert proposed["items"][0] == {
        "code": "PN",
        "name": "Podatek od nieruchomości",
        "techName": "podatek_od_nieruchomosci",
    }
