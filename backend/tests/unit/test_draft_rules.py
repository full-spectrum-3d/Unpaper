import pytest

from app.models.document import DocumentModel
from app.pipeline.draft_rules import (
    applicant_field_reason,
    covered_by,
    is_statement,
    statements_from_document,
    variant_choices,
)


def _doc(*blocks: tuple[str, str]) -> DocumentModel:
    return DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"id": f"b{n}", "kind": kind, "text": text}
                        for n, (kind, text) in enumerate(blocks, 1)
                    ],
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "label",
    [
        "Imię i nazwisko wnioskodawcy",
        "Nazwisko i imię/Nazwa firmy",
        "Adres zamieszkania",
        "Nr telefonu",
        "nr telefonu/adres e-mail",
        "PESEL",
        "Numer telefonu (opcjonalnie)",
        "Miejscowość i data",
        "Czytelny podpis wnioskodawcy",
        "Podpis wnioskodawcy lub osoby upoważnionej",
        "Data sporządzenia wniosku",
    ],
)
def test_applicant_labels_detected(label: str) -> None:
    assert applicant_field_reason(label, ["Podstawowe dane", "Informacje o wniosku"])


@pytest.mark.parametrize(
    "label",
    [
        "Miejscowość",
        "Ulica",
        "Obręb",
        "Adres",
        "Nazwa",
        "Data",
        "Osoba odpowiedzialna",
        "Imię i nazwisko kandydata",
        "Czy wnioskodawca jest właścicielem?",
        "Data urodzenia",
    ],
)
def test_subject_labels_kept(label: str) -> None:
    assert applicant_field_reason(label, ["Lokalizacja budynku"]) is None


def test_personal_fields_of_other_person_kept() -> None:
    assert applicant_field_reason("Imię", ["Dane sportowca"]) is None
    assert applicant_field_reason("Nr telefonu", ["Osoba odpowiedzialna"]) is None
    assert applicant_field_reason("Telefon wnioskodawcy", ["Osoba odpowiedzialna"])
    assert applicant_field_reason("Imię", ["Dane osobowe"])


def test_statement_with_list_items_joined() -> None:
    doc = _doc(
        ("paragraph", "Cel wynajęcia świetlicy: ………"),
        ("paragraph", "4. Jednocześnie oświadczam, że:"),
        ("paragraph", "zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej,"),
        ("paragraph", "zobowiązuję się do przestrzegania przepisów BHP."),
        ("input_placeholder", "……………"),
        ("paragraph", "(czytelny podpis wnioskodawcy)"),
    )
    assert statements_from_document(doc) == [
        "Jednocześnie oświadczam, że: zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej, "
        "zobowiązuję się do przestrzegania przepisów BHP."
    ]


def test_statements_skip_fields_data_consents_and_duplicates() -> None:
    doc = _doc(
        ("paragraph", "1) Ja niżej podpisany ………… oświadczam, że jestem rodzicem"),
        ("paragraph", "1) Wyrażam zgodę na przetwarzanie moich danych osobowych."),
        ("paragraph", "2) Oświadczam, że zapoznałem się z regulaminem."),
        ("paragraph", "Oświadczam, że zapoznałem się z regulaminem."),
        ("heading", "Oświadczam"),
        ("paragraph", "Do wniosku należy dołączyć oświadczenie."),
    )
    assert statements_from_document(doc) == ["Oświadczam, że zapoznałem się z regulaminem."]


def test_statements_ignore_rodo_clause() -> None:
    doc = _doc(
        ("paragraph", "Zgodnie z art. 13 ust. 1 i 2 rozporządzenia (UE) 2016/679 informujemy, że"),
        ("paragraph", "Oświadczam, że przyjmuję do wiadomości powyższe."),
        ("input_placeholder", "………"),
        ("paragraph", "Oświadczam, że dane są prawdziwe."),
    )
    assert statements_from_document(doc) == ["Oświadczam, że dane są prawdziwe."]


def test_covered_by_tolerates_typos() -> None:
    text = "w czasie najmu odpowiadam za ład i porządek na ternie przyległym do świetlicy"
    assert covered_by("Na terenie przyległym do świetlicy odpowiadam za ład", text) < 0.8
    assert (
        covered_by("W czasie najmu odpowiadam za ład i porządek na terenie przyległym", text) > 0.9
    )


@pytest.mark.parametrize(
    ("label", "context"),
    [
        ("Miejscowość", ["Adres zamieszkania"]),
        ("Nr domu", ["Adres siedziby lub miejsca zamieszkania wnioskodawcy"]),
        ("Kod pocztowy", ["B.4 Adres do korespondencji"]),
        ("Województwo", ["Dane wnioskodawcy"]),
        ("Adres poczty elektronicznej", ["Dane kontaktowe"]),
    ],
)
def test_address_parts_in_applicant_section_detected(label: str, context: list[str]) -> None:
    assert applicant_field_reason(label, context)


@pytest.mark.parametrize(
    ("label", "context"),
    [
        ("Miejscowość", ["Adres nieruchomości"]),
        ("Ulica", ["Lokalizacja pasa drogowego"]),
        ("Kod pocztowy", ["Dane identyfikacyjne współmałżonka"]),
        ("Nr domu", ["Adres zamieszkania pełnomocnika"]),
        ("Rasa psa", ["Dane wnioskodawcy"]),
    ],
)
def test_address_parts_elsewhere_kept(label: str, context: list[str]) -> None:
    assert applicant_field_reason(label, context) is None


def test_statement_after_position_number_is_a_field() -> None:
    doc = _doc(
        ("paragraph", "35."),
        ("paragraph", "Oświadczam, że nieruchomość wyposażona jest w kompostownik."),
        ("paragraph", "Oświadczam, że dane są prawdziwe."),
    )
    assert statements_from_document(doc) == ["Oświadczam, że dane są prawdziwe."]


def test_is_statement() -> None:
    assert is_statement("2. Oświadczam, że psy nie będą wykorzystywane do polowań")
    assert not is_statement("Data szczepienia")


def test_variant_choices() -> None:
    doc = _doc(
        ("paragraph", "o wynajęcie/użyczenie* świetlicy wiejskiej"),
        ("paragraph", "Proszę o wynajem/użyczenie* świetlicy"),
        ("paragraph", "hodowanie/utrzymywanie* charta/chartów*"),
        ("paragraph", "metryka**, zapoznałem/am się, imię/nazwisko*"),
    )
    assert variant_choices(doc) == [["wynajęcie", "użyczenie"], ["hodowanie", "utrzymywanie"]]


def test_subject_section_title_wins_over_applicant_words() -> None:
    assert applicant_field_reason("Miejscowość", ["Dane identyfikacyjne nieruchomości"]) is None
    assert applicant_field_reason("Ulica", ["Adres zamieszkania", "Informacje o budynku"])


def test_applicant_person_section_is_not_other_person() -> None:
    assert applicant_field_reason("Nazwisko i imię", ["Osoba wnioskodawca"])


def test_full_and_short_names_are_applicant_data() -> None:
    assert applicant_field_reason("Nazwisko/Nazwa pełna", ["Podstawowe dane"])
    assert applicant_field_reason("Pierwsze imię/ Nazwa skrócona", ["Podstawowe dane"])
