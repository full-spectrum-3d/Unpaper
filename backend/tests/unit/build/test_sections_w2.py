"""Sekcje szablonowe: checkboxy braku danych adresu, readOnlyWhen, czasownik podmiotu, opłata."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.models.draft import ApplicantKind, FormDraft
from app.models.form import FieldType, to_document_format
from app.pipeline.build import BuildOptions, build_form
from app.pipeline.build.ir import AllOf, Eq, Not, SectionNode
from app.pipeline.build.sections import (
    APPLICANT_OPTIONS,
    applicant_page_sections,
    instantiate,
    load_template,
)
from app.pipeline.verify import verify_form

ALL_KINDS: list[ApplicantKind] = ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]
LEGAL = APPLICANT_OPTIONS["LEGAL_ENTITY"]


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


def walk(node: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "techName" in node and "type" in node:
            found.append(node)
        for value in node.values():
            found += walk(value)
    elif isinstance(node, list):
        for value in node:
            found += walk(value)
    return found


# --- B1: checkboxy braku danych adresowych ---

# klucz checkboxa -> (etykieta, klucz pola, które zasłania)
_NO_DATA = {
    "brak_nazwy_ulicy_zagranica": ("Brak nazwy ulicy", "ulica_zagranica"),
    "brak_kodu_pocztowego_zagranica": ("Brak kodu pocztowego", "kod_pocztowy_zagranica"),
    "brak_nazwy_ulicy": ("Brak nazwy ulicy", "ulica"),
    "brak_numeru_lokalu": ("Brak numeru lokalu", "numer_lokalu"),
}


@pytest.mark.parametrize("suffix", ["", "_siedziba", "_inna_osoba"])
def test_address_has_no_data_checkboxes(suffix: str) -> None:
    section = instantiate(
        load_template("address.json"),
        key="adres",
        suffix=suffix,
        params={"title": "Adres", "section_tech_name": "adres"},
    )
    keys = [f.key for f in section.fields]
    assert len({f.tech_name for f in section.fields}) == len(keys)
    for base, (label, target) in _NO_DATA.items():
        box = next(f for f in section.fields if f.key == f"adres.{base}")
        assert box.type is FieldType.CHECKBOX
        assert box.options == [label]
        assert box.validation == []
        assert box.tech_name.endswith(suffix) or box.tech_name.endswith("_zagranica")
        guarded = next(f for f in section.fields if f.key == f"adres.{target}")
        assert keys.index(box.key) == keys.index(guarded.key) + 1
        # pole znika po zaznaczeniu checkboxa
        hidden = Not(Eq(box.key, label))
        if isinstance(guarded.show_when, AllOf):
            assert hidden in guarded.show_when.items
        else:
            assert guarded.show_when == hidden


def test_no_data_checkbox_in_built_form() -> None:
    result = build_form(make_draft(), BuildOptions(rodo_clause_url="https://bip.example/rodo"))
    assert not result.warnings
    form = result.form.to_import_json()
    verified = verify_form(form, autofix=False)
    assert verified.valid, verified.errors
    fields = {f["techName"]: f for f in walk(form)}
    box = fields["brak_nazwy_ulicy"]
    assert box["type"] == "CHECKBOX"
    assert box["options"][0]["name"] == "Brak nazwy ulicy"
    query = fields["ulica"]["states"][0]["query"]
    assert "Brak nazwy ulicy" in query
    assert "$not(" in query
    assert "brak_nazwy_ulicy" in query
    assert "Brak numeru lokalu" in fields["numer_lokalu"]["states"][0]["query"]


# --- B2: readOnlyWhen w szablonach ---


def test_template_read_only_when() -> None:
    template = {
        "title": "T",
        "techName": "t",
        "fields": [
            {"key": "a", "type": "TEXT_FIELD", "title": "A", "techName": "a"},
            {
                "key": "b",
                "type": "TEXT_FIELD",
                "title": "B",
                "techName": "b",
                "readOnlyWhen": {"not": {"eq": ["a", "x"]}},
            },
        ],
    }
    section = instantiate(template, key="s")
    assert section.fields[1].read_only_when == Not(Eq("s.a", "x"))
    assert section.fields[0].read_only_when is None


# --- D2: czasownik według tytułu formularza ---


@pytest.mark.parametrize(
    ("title", "verb"),
    [
        ("Wniosek o X", "wnioskujesz"),
        ("Zgłoszenie zmiany", "zgłaszasz"),
        ("Deklaracja podatkowa", "deklarujesz"),
        ("Oświadczenie o Y", "wnioskujesz"),
        ("  zgłoszenie  ", "zgłaszasz"),
        ("Podanie", "wnioskujesz"),
    ],
)
def test_subject_verb_follows_form_title(title: str, verb: str) -> None:
    draft = make_draft(title=title, applicant_kinds=ALL_KINDS)
    section = by_tech(applicant_page_sections(draft, BuildOptions()), "podmiot_wniosku")
    who, role = section.fields
    ascii_verb = verb.replace("ł", "l")
    assert who.title == f"Wybierz, w czyim imieniu {verb}"
    assert who.tech_name == f"wybierz_w_czyim_imieniu_{ascii_verb}"
    assert role.title == f"Wybierz, jako kto {verb}"
    assert role.tech_name == f"wybierz_jako_kto_{ascii_verb}"
    assert role.show_when == Eq(who.key, LEGAL)


def test_subject_verb_in_built_form_keeps_states_consistent() -> None:
    draft = make_draft(title="Zgłoszenie zmiany", applicant_kinds=ALL_KINDS)
    result = build_form(draft, BuildOptions(rodo_clause_url="https://bip.example/rodo"))
    assert not result.warnings
    form = result.form.to_import_json()
    assert verify_form(form, autofix=False).valid
    role = next(f for f in walk(form) if f["techName"] == "wybierz_jako_kto_zglaszasz")
    assert "wybierz_w_czyim_imieniu_zglaszasz" in role["states"][0]["query"]


# --- D3: opłata skarbowa zgodna ze standardem ---


@pytest.mark.parametrize("name", ["stamp_duty_v1.json", "stamp_duty_v2.json"])
def test_stamp_duty_matches_standard(name: str) -> None:
    section = instantiate(load_template(name), key="k", params={"form_title": "Wniosek"})
    block = next(f for f in section.fields if f.type is FieldType.TEXT_BLOCK)
    assert (
        "<p>Dodaj plik z potwierdzeniem przelewu. Znajdziesz go na stronie lub w aplikacji "
        "swojego banku.</p>" in block.description_html
    )
    upload = next(f for f in section.fields if f.type is FieldType.FILE_UPLOADER)
    assert ".pdf" in upload.description_html
    for other in (".jpg", ".png", ".jpeg"):
        assert other not in upload.description_html


# --- C5: required zgód zgodnie ze wzorcami ---


def test_consent_required_matches_reference_layout() -> None:
    root = Path(__file__).parents[4] / "wymagania"
    for name in (
        "konfiguracja_form_wniosekOStwierdzenieNadplatyPodatku.json",
        "konfiguracja_form_wniosekOUstalenieNumeruPorzadkowegoNieruchomosci.json",
    ):
        raw = json.loads((root / name).read_text(encoding="utf-8"))
        reference = to_document_format(raw)[0]
        config = next(
            f["consentSectionConfig"] for f in walk(reference) if f.get("type") == "CONSENT_SECTION"
        )
        # wzorce mają `required` per zgoda; po tłumaczeniu jest na poziomie sekcji zgód
        assert set(config) == {"consents", "required", "files"}
        assert config["required"] is True
        assert all(set(c) == {"description"} for c in config["consents"])
    form = build_form(make_draft(statements=["A"]), BuildOptions()).form.to_import_json()
    ours = next(f for f in walk(form) if f.get("type") == "CONSENT_SECTION")
    # OpisImportowanegoPlikuJSON.md: `required` tylko na poziomie consentSectionConfig
    assert set(ours["consentSectionConfig"]) == {"consents", "required", "files"}
    assert ours["consentSectionConfig"]["required"] is True
    assert ours["consentSectionConfig"]["files"] == []
    assert all(set(c) == {"description"} for c in ours["consentSectionConfig"]["consents"])
