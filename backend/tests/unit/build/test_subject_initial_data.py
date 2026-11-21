"""Dane inicjalne z rejestrów dla pól przedmiotu sprawy (spec §8.5)."""

from typing import Any

import pytest

from app.models.draft import DraftField, DraftPage, DraftSection, FieldKind, FormDraft
from app.models.form import EXTERNAL_SYSTEM, FieldType, TabType
from app.pipeline.build import build_form
from app.pipeline.build.fields import map_draft_field
from app.pipeline.build.initial_data import apply_initial_data, initial_data_ref
from app.pipeline.build.ir import FieldNode, PageNode, SectionNode
from app.pipeline.verify import verify_form

# --- A2: dane inicjalne ------------------------------------------------------


def _draft(label: str, kind: FieldKind, **kwargs: list[str]) -> DraftField:
    return DraftField(id="f1", label=label, kind=kind, required=False, **kwargs)


@pytest.mark.parametrize(
    ("label", "kind", "ref"),
    [
        ("Data urodzenia", "date", "PESEL.birthDate"),
        ("Data urodzenia:", "date", "PESEL.birthDate"),
        ("Miejsce urodzenia", "short_text", "PESEL.birthPlace"),
        ("Imię matki", "short_text", "PESEL.motherName"),
        ("Imię ojca", "short_text", "PESEL.fatherName"),
        ("Nazwisko rodowe", "short_text", "PESEL.familyName"),
        ("Drugie imię", "short_text", "PESEL.secondName"),
        ("Stan cywilny", "short_text", "PESEL.maritalStatus"),
        ("Ulica zameldowania", "short_text", "PESEL_ADDRESS.permanentAddressStreet"),
        (
            "Adres zameldowania: Kod pocztowy",
            "short_text",
            "PESEL_ADDRESS.permanentAddressPostalCode",
        ),
        (
            "Tymczasowy adres zameldowania: Numer domu",
            "short_text",
            "PESEL_ADDRESS.temporaryAddressHouseNumber",
        ),
    ],
)
def test_initial_data_hits(label: str, kind: FieldKind, ref: str) -> None:
    node, _ = map_draft_field(_draft(label, kind), key="p1.s1.f1")
    assert initial_data_ref(node, section_title="Dane wnioskodawcy", repeating=False) == ref


@pytest.mark.parametrize(
    ("label", "kind"),
    [
        ("Data urodzenia dziecka", "date"),
        ("Data urodzenia małżonka", "date"),
        ("Data urodzenia zmarłego", "date"),
        ("Data urodzenia pełnomocnika", "date"),
        ("Data urodzenia innej osoby", "date"),
        ("Data urodzenia", "short_text"),  # niezgodny typ
        ("Płeć", "single_choice"),
        ("Adres zameldowania", "short_text"),  # niejednoznaczny
        ("Ulica", "short_text"),
        ("Imię", "short_text"),
        ("Imię matki dziecka", "short_text"),
        ("Data urodzenia lub zgonu", "date"),
    ],
)
def test_initial_data_misses(label: str, kind: FieldKind) -> None:
    options = {"options": ["a", "b"]} if kind == "single_choice" else {}
    node, _ = map_draft_field(_draft(label, kind, **options), key="p1.s1.f1")
    assert initial_data_ref(node, section_title="Dane wnioskodawcy", repeating=False) is None


def test_initial_data_skipped_in_repeating_or_foreign_section() -> None:
    node, _ = map_draft_field(_draft("Data urodzenia", "date"), key="p1.s1.f1")
    assert initial_data_ref(node, section_title="Osoby", repeating=True) is None
    assert initial_data_ref(node, section_title="Dane dziecka", repeating=False) is None


def _page(*fields: FieldNode, repeating: bool = False) -> list[PageNode]:
    section = SectionNode(
        "p1.s1",
        FieldType.REPEATING_SECTION if repeating else FieldType.SECTION,
        "Dane",
        "dane",
        fields=list(fields),
    )
    return [PageNode("p1", "Strona", TabType.MAIN, [section])]


def test_apply_initial_data_fills_subject_field() -> None:
    node, _ = map_draft_field(_draft("Data urodzenia", "date"), key="p1.s1.f1")
    assert apply_initial_data(_page(node)) == []
    assert node.default_value == "PESEL.birthDate"
    assert node.default_value_type == EXTERNAL_SYSTEM
    assert node.read_only is True


def test_apply_initial_data_ignores_non_subject_keys_and_duplicates() -> None:
    first = map_draft_field(_draft("Imię matki", "short_text"), key="p1.s1.f1")[0]
    second = map_draft_field(_draft("Imię matki", "short_text"), key="p1.s1.f2")[0]
    foreign = map_draft_field(_draft("Imię ojca", "short_text"), key="kontakt.x")[0]
    apply_initial_data(_page(first, second, foreign))
    assert first.default_value == "PESEL.motherName"
    assert second.default_value is None
    assert foreign.default_value is None


def test_apply_initial_data_skips_repeating_section() -> None:
    node = map_draft_field(_draft("Data urodzenia", "date"), key="p1.s1.f1")[0]
    apply_initial_data(_page(node, repeating=True))
    assert node.default_value is None


def test_built_form_passes_verification() -> None:
    draft = FormDraft(
        title="Wniosek o zaświadczenie",
        authority_kind="URZAD",
        authority_name="Urząd",
        applicant_kinds=["SELF"],
        subject_pages=[
            DraftPage(
                title="Sprawa",
                sections=[
                    DraftSection(
                        title="Dane osoby",
                        repeating=False,
                        fields=[
                            DraftField(id="f1", label="Data urodzenia", kind="date", required=True),
                            DraftField(
                                id="f2", label="Imię matki", kind="short_text", required=False
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    form = build_form(draft).form.to_import_json()
    found: dict[str, dict[str, Any]] = {}

    def collect(field: dict[str, Any]) -> None:
        found[field["techName"]] = field
        for child in field["repeatingSectionGrid"]:
            collect(child["field"])

    for tab in form["tabs"]:
        for question in tab["questions"]:
            collect(question["field"])
    assert found["data_urodzenia"]["defaultValue"] == "PESEL.birthDate"
    assert found["data_urodzenia"]["readOnly"] is True
    assert verify_form(form, autofix=False).valid


def test_form_for_another_person_gets_no_subject_registry_data() -> None:
    # Wniosek składany także w cudzym imieniu: „Data urodzenia” może dotyczyć innej osoby.
    draft = FormDraft(
        title="Wniosek o zaświadczenie",
        authority_kind="URZAD",
        authority_name="Urząd",
        applicant_kinds=["SELF", "OTHER_PERSON"],
        subject_pages=[
            DraftPage(
                title="Sprawa",
                sections=[
                    DraftSection(
                        title="Dane osoby",
                        repeating=False,
                        fields=[
                            DraftField(id="f1", label="Data urodzenia", kind="date", required=True)
                        ],
                    )
                ],
            )
        ],
    )
    assert "PESEL.birthDate" not in build_form(draft).form.model_dump_json()
