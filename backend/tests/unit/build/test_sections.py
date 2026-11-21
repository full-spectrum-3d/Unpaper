import importlib.resources
import json

import pytest

from app.core.config import Settings
from app.models.draft import ApplicantKind, FormDraft
from app.models.form import FieldType, Validator
from app.pipeline.build import BuildOptions
from app.pipeline.build.ir import AllOf, AnyOf, Eq, FieldNode, SectionNode
from app.pipeline.build.sections import (
    APPLICANT_OPTIONS,
    ROLE_CHOICE_KEY,
    SUBJECT_CHOICE_KEY,
    applicant_page_sections,
    contact_page_sections,
    finish_page_sections,
    instantiate,
    load_template,
)

ALL_KINDS: list[ApplicantKind] = ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]
LEGAL = APPLICANT_OPTIONS["LEGAL_ENTITY"]
OTHER = APPLICANT_OPTIONS["OTHER_PERSON"]


def make_draft(**kwargs: object) -> FormDraft:
    data: dict[str, object] = {
        "title": "Wniosek o stwierdzenie nadpłaty podatku",
        "authority_kind": "URZAD",
        "authority_name": "Urząd Gminy",
        "applicant_kinds": ["SELF"],
        "subject_pages": [],
    }
    data.update(kwargs)
    return FormDraft.model_validate(data)


def by_tech(sections: list[SectionNode], tech_name: str) -> SectionNode:
    return next(s for s in sections if s.tech_name == tech_name)


def field_by_tech(section: SectionNode, tech_name: str) -> FieldNode:
    return next(f for f in section.fields if f.tech_name == tech_name)


def test_all_applicant_kinds_section_order() -> None:
    draft = make_draft(
        applicant_kinds=ALL_KINDS,
        authority_kind="URZAD",
        authority_name="Urząd Gminy Ulan-Majorat",
    )
    sections = applicant_page_sections(draft, BuildOptions())
    assert [s.title for s in sections] == [
        "Urząd, do którego jest składany wniosek",
        "Podmiot wniosku",
        "Twoje dane",
        "Adres zamieszkania",
        "Dane podmiotu",
        "Adres siedziby",
        "Potwierdzenie, że jesteś reprezentantem",
        "Dane innej osoby",
        "Adres zamieszkania innej osoby",
        "Pełnomocnictwo",
        "Opłata skarbowa",
        "Opłata skarbowa za pełnomocnictwo",
    ]
    assert [s.tech_name for s in sections] == [
        "urzad_do_ktorego_jest_skladany_wniosek",
        "podmiot_wniosku",
        "twoje_dane",
        "adres_zamieszkania",
        "dane_podmiotu",
        "adres_siedziby",
        "potwierdzenie_ze_jestes_reprezentantem",
        "dane_innej_osoby",
        "adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem",
        "pelnomocnictwo",
        "oplata_skarbowa_pelnomocnictwo_1",
        "oplata_skarbowa_pelnomocnictwo_2",
    ]
    subject = by_tech(sections, "podmiot_wniosku")
    assert [f.key for f in subject.fields] == [SUBJECT_CHOICE_KEY, ROLE_CHOICE_KEY]
    assert subject.fields[0].options == list(APPLICANT_OPTIONS.values())
    assert subject.fields[1].show_when == Eq(SUBJECT_CHOICE_KEY, LEGAL)
    assert by_tech(sections, "dane_podmiotu").show_when == Eq(SUBJECT_CHOICE_KEY, LEGAL)
    assert by_tech(sections, "potwierdzenie_ze_jestes_reprezentantem").show_when == AllOf(
        (Eq(SUBJECT_CHOICE_KEY, LEGAL), Eq(ROLE_CHOICE_KEY, "Reprezentant"))
    )
    assert by_tech(sections, "dane_innej_osoby").show_when == Eq(SUBJECT_CHOICE_KEY, OTHER)
    assert by_tech(sections, "oplata_skarbowa_pelnomocnictwo_1").show_when == Eq(
        SUBJECT_CHOICE_KEY, OTHER
    )
    assert by_tech(sections, "twoje_dane").show_when is None


def test_self_only() -> None:
    draft = make_draft(applicant_kinds=["SELF"])
    sections = applicant_page_sections(draft, BuildOptions())
    assert [s.title for s in sections] == [
        "Urząd, do którego jest składany wniosek",
        "Twoje dane",
        "Adres zamieszkania",
    ]


def test_person_kinds_only() -> None:
    draft = make_draft(applicant_kinds=["SELF", "OTHER_PERSON"])
    sections = applicant_page_sections(draft, BuildOptions())
    subject = by_tech(sections, "podmiot_wniosku")
    assert len(subject.fields) == 1
    assert subject.fields[0].options == ["Swoim", "Innej osoby"]
    assert subject.fields[0].validation == [Validator.REQUIRED]
    assert by_tech(sections, "pelnomocnictwo").show_when == Eq(SUBJECT_CHOICE_KEY, OTHER)
    assert all(s.tech_name != "oplata_skarbowa_pelnomocnictwo_2" for s in sections)


def test_organ_authority() -> None:
    draft = make_draft(authority_kind="ORGAN", authority_name="Wójt Gminy Elbląg")
    first = applicant_page_sections(draft, BuildOptions())[0]
    assert first.title == "Organ, do którego jest składany wniosek"
    assert first.tech_name == "organ_do_ktorego_jest_skladany_wniosek"
    field = first.fields[0]
    assert field.title == "Nazwa organu"
    assert field.tech_name == "nazwa_organu"
    assert field.default_value == "Wójt Gminy Elbląg"
    assert field.read_only is True
    assert field.validation == []


def test_address_fields_match_reference() -> None:
    draft = make_draft(applicant_kinds=["SELF", "LEGAL_ENTITY"])
    sections = applicant_page_sections(draft, BuildOptions())
    seat = by_tech(sections, "adres_siedziby")
    assert [f.tech_name for f in seat.fields] == [
        "kraj_siedziba",
        "miejscowosc_siedziba_zagranica",
        "kod_pocztowy_siedziba_zagranica",
        "ulica_siedziba_zagranica",
        "wojewodztwo_siedziba",
        "kod_pocztowy_siedziba",
        "ulica_siedziba",
        "numer_budynku_siedziba",
        "numer_lokalu_siedziba",
    ]
    assert all(f.initial_data is None for f in seat.fields)
    home = by_tech(sections, "adres_zamieszkania")
    assert field_by_tech(home, "kod_pocztowy").initial_data == "MLPZ.postCode"
    assert field_by_tech(home, "kod_pocztowy").validation == [
        Validator.REQUIRED,
        Validator.ZIP_CODE,
    ]
    assert field_by_tech(home, "numer_lokalu").validation == []
    kraj = field_by_tech(home, "kraj")
    assert kraj.dictionary_name == "Kraje"
    assert kraj.default_value == ["Polska"]
    assert kraj.multi_level_tree is False
    teryt = field_by_tech(home, "wojewodztwo")
    assert teryt.title == "TERYT_4G_DOWODOWY"
    assert teryt.multi_level_tree is True
    assert teryt.default_value == []
    assert field_by_tech(home, "ulica_zagranica").show_when is not None
    assert field_by_tech(home, "ulica").show_when == Eq(kraj.key, "Polska")


def test_applicant_has_single_home_address_with_initial_data() -> None:
    sections = applicant_page_sections(make_draft(applicant_kinds=ALL_KINDS), BuildOptions())
    homes = [s for s in sections if s.title == "Adres zamieszkania"]
    assert [s.tech_name for s in homes] == ["adres_zamieszkania"]
    assert field_by_tech(homes[0], "kod_pocztowy").initial_data == "MLPZ.postCode"
    assert not any("zameldowania" in s.tech_name for s in sections)
    assert not any("korespondencyjny" in s.tech_name for s in sections)


def test_identity_source() -> None:
    draft = make_draft(applicant_kinds=["SELF"])
    sections = applicant_page_sections(draft, BuildOptions(identity_source="PESEL"))
    imie = field_by_tech(by_tech(sections, "twoje_dane"), "imie")
    assert imie.initial_data == "PESEL.name"
    assert imie.read_only is True


def test_power_of_attorney_condition() -> None:
    draft = make_draft(applicant_kinds=ALL_KINDS)
    section = by_tech(applicant_page_sections(draft, BuildOptions()), "pelnomocnictwo")
    assert section.show_when == AnyOf(
        (
            Eq(SUBJECT_CHOICE_KEY, "Innej osoby"),
            AllOf(
                (
                    Eq(SUBJECT_CHOICE_KEY, "Osoby prawnej lub jednostki organizacyjnej"),
                    Eq(ROLE_CHOICE_KEY, "Pełnomocnik"),
                )
            ),
        )
    )


def test_form_title_escaped_in_stamp_duty() -> None:
    draft = make_draft(title="Wniosek <b>", applicant_kinds=ALL_KINDS)
    sections = applicant_page_sections(draft, BuildOptions())
    for tech in ("oplata_skarbowa_pelnomocnictwo_1", "oplata_skarbowa_pelnomocnictwo_2"):
        block = next(f for f in by_tech(sections, tech).fields if f.type is FieldType.TEXT_BLOCK)
        html = block.description_html
        assert "Wniosek &lt;b&gt; – opłata skarbowa za pełnomocnictwo" in html  # noqa: RUF001
        assert "<img" not in html
        assert "style=" not in html
        assert "<span" not in html
        assert block.title == ""
        assert block.validation == []


def test_stamp_duty_uses_normalized_title() -> None:
    draft = make_draft(title="  Wniosek \n  o   X\t", applicant_kinds=ALL_KINDS)
    sections = applicant_page_sections(draft, BuildOptions())
    for tech in ("oplata_skarbowa_pelnomocnictwo_1", "oplata_skarbowa_pelnomocnictwo_2"):
        block = next(f for f in by_tech(sections, tech).fields if f.type is FieldType.TEXT_BLOCK)
        assert "„Wniosek o X – opłata skarbowa" in block.description_html  # noqa: RUF001


def test_consents() -> None:
    options = BuildOptions(rodo_clause_url="https://example.org/rodo")
    sections = contact_page_sections(make_draft(), options, [])
    assert [s.title for s in sections] == ["Dane do kontaktu", "Zgoda"]
    consent = sections[1].fields[0]
    assert consent.type is FieldType.CONSENT_SECTION
    assert consent.title == ""
    assert len(consent.consents) == 1
    assert 'href="https://example.org/rodo"' in consent.consents[0].description_html
    assert consent.consents[0].required is True
    assert not consent.select_all_enabled

    draft = make_draft(statements=["Oświadczam, że dane są <prawdziwe>.", "Drugie."])
    sections = contact_page_sections(draft, BuildOptions(), [])
    assert sections[1].title == "Zgody i oświadczenia"
    assert sections[1].tech_name == "zgody_i_oswiadczenia"
    consent = sections[1].fields[0]
    assert len(consent.consents) == 3
    assert consent.select_all_enabled is True
    assert all(c.required for c in consent.consents)
    assert "<a" not in consent.consents[0].description_html
    assert (
        consent.consents[1].description_html == "<p>Oświadczam, że dane są &lt;prawdziwe&gt;.</p>"
    )


def test_contact_and_attachments() -> None:
    sections = contact_page_sections(make_draft(), BuildOptions(), ["Kopia decyzji", "Umowa"])
    assert [s.tech_name for s in sections][:2] == ["dane_do_kontaktu", "zalaczniki"]
    contact = sections[0]
    assert [f.tech_name for f in contact.fields] == [
        "numer_kierunkowy",
        "numer_telefonu",
        "adres_e_mail",
    ]
    assert all(f.validation in ([], [Validator.EMAIL]) for f in contact.fields)
    files = sections[1].fields
    assert [f.tech_name for f in files] == ["kopia_decyzji", "umowa"]
    assert files[0].type is FieldType.FILE_UPLOADER
    assert files[0].validation == [Validator.REQUIRED]
    assert files[0].description_html.endswith("Maksymalna liczba plików: 1.</p>")


@pytest.mark.parametrize("signed", [True, False])
def test_finish_preview_text(signed: bool) -> None:
    sections = finish_page_sections(make_draft(), BuildOptions(signed=signed))
    block = sections[-1].fields[0]
    assert sections[-1].tech_name == "podglad_uzupelnionego_wniosku"
    assert ("Zanim przejdziesz do wyboru" in block.description_html) is signed
    assert ("Zanim wyślesz formularz" in block.description_html) is not signed


def test_finish_page_has_only_preview_and_info_section_style() -> None:
    sample = finish_page_sections(make_draft(), BuildOptions())
    assert [s.tech_name for s in sample] == ["podglad_uzupelnionego_wniosku"]
    assert sample[0].fields[0].type is FieldType.TEXT_BLOCK
    options = BuildOptions(finish_page_style="info_section")
    sections = finish_page_sections(make_draft(), options)
    assert [s.tech_name for s in sections] == ["podglad_uzupelnionego_wniosku"]
    assert all(f.type is FieldType.INFO_SECTION for s in sections for f in s.fields)


def test_build_options_from_settings() -> None:
    settings = Settings(
        app_env="development",
        auth_enabled=False,
        initial_data_identity_source="PESEL",
        finish_page_style="info_section",
        max_sections_per_page=3,
    )
    options = BuildOptions.from_settings(settings)
    assert (options.identity_source, options.finish_page_style) == ("PESEL", "info_section")
    assert options.max_sections_per_page == 3
    assert options.rodo_clause_url is None
    with_url = Settings(
        app_env="development", auth_enabled=False, rodo_clause_url="https://example.test/rodo"
    )
    assert BuildOptions.from_settings(with_url).rodo_clause_url == "https://example.test/rodo"
    assert isinstance(hash(options), int)
    assert isinstance(options.id_factory(), str)


def test_every_template_instantiates() -> None:
    folder = importlib.resources.files("app.resources") / "templates"
    names = sorted(p.name for p in folder.iterdir() if p.name.endswith(".json"))
    assert len(names) == 12
    params = {
        "title": "Tytuł",
        "label": "Etykieta",
        "section_tech_name": "tytul",
        "field_tech_name": "etykieta",
        "form_title": "Wniosek",
        "text": "Tekst",
    }
    for name in names:
        template = load_template(name)
        assert json.loads((folder / name).read_text(encoding="utf-8")) == template
        section = instantiate(template, key="k", params=params)
        assert section.type is FieldType.SECTION
        assert section.fields
        assert all(f.key.startswith("k.") for f in section.fields)
        assert "{" not in section.title + section.tech_name
