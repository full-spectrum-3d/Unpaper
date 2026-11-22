import copy
from pathlib import Path
from typing import Any

import pytest

from app.models.document import DocumentModel
from app.models.draft import DraftField, FormDraft
from app.pipeline.draft_normalize import matches_text, normalize_draft
from tests.unit.test_draft import _draft

DOC = DocumentModel.model_validate_json(
    (Path(__file__).parent.parent / "fixtures" / "documents" / "wniosek1.json").read_text(
        encoding="utf-8"
    )
)


def _make(mutate: Any = None) -> FormDraft:
    d = copy.deepcopy(_draft())
    # Pola f5/f6 (pytanie o budowę) nie występują w blankiecie - tu ich nie chcemy.
    d["subject_pages"][0]["sections"][0]["fields"] = d["subject_pages"][0]["sections"][0]["fields"][
        :4
    ]
    if mutate:
        mutate(d)
    return FormDraft.model_validate(d)


def _fields(d: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = d["subject_pages"][0]["sections"][0]["fields"]
    return fields


def _field(draft: FormDraft, fid: str) -> DraftField:
    return next(f for _, f in draft.iter_fields() if f.id == fid)


def _codes(warnings: list[Any]) -> list[str]:
    return [w.code for w in warnings]


def _doc_with(text: str) -> DocumentModel:
    return DocumentModel.model_validate(
        {
            "source": {"method": "docx", "pages": 1},
            "pages": [{"number": 1, "blocks": [{"id": "b1", "kind": "paragraph", "text": text}]}],
        }
    )


def test_valid_draft_unchanged() -> None:
    draft = _make()
    out, warnings = normalize_draft(draft, DOC)
    assert out == draft and warnings == []


def test_condition_on_downgraded_choice_is_dropped() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {"id": "f5", "label": "Numer ewidencyjny", "kind": "single_choice", "required": True,
             "options": ["Tak"]}
        )  # fmt: skip
        _fields(d)[3]["visible_when"] = [{"field_id": "f5", "op": "equals", "value": "Tak"}]

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _field(out, "f5").kind == "short_text" and _field(out, "f5").options == []
    assert _field(out, "f4").visible_when == []
    assert set(_codes(warnings)) == {"W15_CHOICE_WITHOUT_OPTIONS"}


def test_single_checkbox_kept() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[3].update(kind="multi_choice", options=["Obręb"])

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _field(out, "f4").kind == "multi_choice" and warnings == []


def _doc_blocks(*blocks: tuple[str, str]) -> DocumentModel:
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


STATEMENT_DOC = _doc_blocks(
    ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
    ("paragraph", "Oświadczam, że jestem właścicielem działki."),
)


def test_statements_come_from_document_not_model() -> None:
    stmt = "Oświadczam, że dane są prawdziwe"
    out, warnings = normalize_draft(_make(lambda d: d.update(statements=[stmt])), STATEMENT_DOC)
    assert out.statements == ["Oświadczam, że jestem właścicielem działki."] and warnings == []


def test_statement_info_field_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {"id": "f5", "label": "Jestem właścicielem działki", "kind": "info", "required": True}
        )

    out, warnings = normalize_draft(_make(mutate), STATEMENT_DOC)
    assert _codes(warnings) == ["W17_STATEMENT_REMOVED"]
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3", "f4"]


def test_applicant_fields_removed_with_their_conditions() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).extend(
            [
                {
                    "id": "f5",
                    "label": "Imię i nazwisko wnioskodawcy",
                    "kind": "single_choice",
                    "required": True,
                    "options": ["A", "B"],
                },
                {"id": "f6", "label": "Nr telefonu", "kind": "short_text", "required": True},
                {"id": "f7", "label": "Miejscowość i data", "kind": "short_text", "required": True},
            ]
        )
        _fields(d)[0]["visible_when"] = [{"field_id": "f5", "op": "equals", "value": "A"}]

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _codes(warnings) == ["W20_APPLICANT_FIELD_REMOVED"] * 3 + ["W21_CONDITION_REMOVED"]
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3", "f4"]
    assert out.subject_pages[0].sections[0].fields[0].visible_when == []


def test_section_of_only_applicant_fields_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"].insert(
            0,
            {
                "title": "Informacje o wniosku",
                "sections": [
                    {
                        "title": "Podstawowe dane",
                        "repeating": False,
                        "fields": [
                            {
                                "id": "f8",
                                "label": "Adres zamieszkania",
                                "kind": "short_text",
                                "required": True,
                            },
                        ],
                    }
                ],
            },
        )

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _codes(warnings) == ["W20_APPLICANT_FIELD_REMOVED"] + ["W18_EMPTY_CONTAINER_REMOVED"] * 2
    assert [p.title for p in out.subject_pages] == ["Informacje o budynku"]


def _title(value: str) -> tuple[str, list[str]]:
    out, warnings = normalize_draft(_make(lambda d: d.update(title=value)), DOC)
    return out.title, _codes(warnings)


def test_uppercase_title_normalized() -> None:
    assert _title("WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO") == (
        "Wniosek o ustalenie numeru porządkowego",
        ["W16_TITLE_CASE_NORMALIZED"],
    )
    assert _title("WNIOSEK O NADANIE NUMERU NIP")[0] == "Wniosek o nadanie numeru NIP"
    assert _title("Wniosek o wydanie zaświadczenia") == ("Wniosek o wydanie zaświadczenia", [])


def test_labels_matched_against_document() -> None:
    _, warnings = normalize_draft(_make(), DOC)
    assert warnings == []

    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[3]["label"] = "Powierzchnia działki"

    _, warnings = normalize_draft(_make(mutate), DOC)
    assert _codes(warnings) == ["W13_FIELD_NOT_IN_DOCUMENT"]
    assert warnings[0].path == "subject_pages[0].sections[0].fields[3]"


def test_page_without_sections_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"].append({"title": "Pusta", "sections": []})

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert [p.title for p in out.subject_pages] == ["Informacje o budynku"]
    assert _codes(warnings) == ["W18_EMPTY_CONTAINER_REMOVED"]


def test_matches_text() -> None:
    assert matches_text("Obręb", "nr działki [POLE] w obrębie [POLE]", 0.6)
    assert matches_text("Numer ewidencyjny działki", "nr ewidencyjny działki [POLE]", 0.6)
    assert not matches_text("Powierzchnia działki", "nr ewidencyjny działki [POLE]", 0.6)


def test_authority_not_in_document_warned() -> None:
    out, warnings = normalize_draft(
        _make(lambda d: d.update(authority_name="Wójt Gminy Elusing")), DOC
    )
    assert _codes(warnings) == ["W19_AUTHORITY_NOT_IN_DOCUMENT"]
    assert out.authority_name == "Wójt Gminy Elusing"


def test_inflected_authority_accepted() -> None:
    doc = _doc_with("Miejscowość Ulica Numer ewidencyjny działki Obręb. Do Urzędu Gminy Elbląg")
    _, warnings = normalize_draft(
        _make(lambda d: d.update(authority_name="Urząd Gminy Elbląg")), doc
    )
    assert warnings == []


def test_duplicate_field_in_section_removed_and_conditions_redirected() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).extend(
            [
                {
                    "id": "f5",
                    "label": "Czy budować?",
                    "kind": "single_choice",
                    "required": True,
                    "options": ["Tak", "Nie"],
                },
                {
                    "id": "f6",
                    "label": "czy  budować?",
                    "kind": "single_choice",
                    "required": True,
                    "options": ["Tak", "Nie"],
                },
            ]
        )
        _fields(d)[0]["visible_when"] = [{"field_id": "f6", "op": "equals", "value": "Tak"}]

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _codes(warnings).count("W25_DUPLICATE_FIELD_REMOVED") == 1
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3", "f4", "f5"]
    assert out.subject_pages[0].sections[0].fields[0].visible_when[0].field_id == "f5"


@pytest.mark.parametrize("name", ["Załącznik 2", "Zał. nr 3", "2)", "załącznik"])
def test_unnamed_attachments_removed(name: str) -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["attachments"] = ["Korekta deklaracji", name]
        _fields(d).append({"id": "f5", "label": name, "kind": "file", "required": True})

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert out.attachments == ["Korekta deklaracji"]
    assert _codes(warnings).count("W26_UNNAMED_ATTACHMENT_REMOVED") == 2
    assert len(list(out.iter_fields())) == 4


def _section(d: dict[str, Any], title: str, *labels: str) -> None:
    n = sum(len(sec["fields"]) for page in d["subject_pages"] for sec in page["sections"])
    fields = [
        {"id": f"f{n + i}", "label": label, "kind": "short_text", "required": True}
        for i, label in enumerate(labels, 1)
    ]
    d["subject_pages"][0]["sections"].append({"title": title, "repeating": False, "fields": fields})


def test_address_parts_in_applicant_section_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _section(d, "Adres zamieszkania wnioskodawcy", "Miejscowość", "Ulica", "Nr domu")
        _section(d, "Dane pełnomocnika", "Miejscowość", "Ulica")

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert out.subject_pages[0].sections[-1].title == "Dane pełnomocnika"
    assert _codes(warnings).count("W20_APPLICANT_FIELD_REMOVED") == 3


PSY_DOC = _doc_blocks(
    ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
    ("paragraph", "Oświadczenia :"),
    ("paragraph", "1. Oświadczam, że psy nie będą wykorzystywane do polowań."),
    ("paragraph", "hodowanie/utrzymywanie* charta/chartów*"),
)


def test_statement_choice_field_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {"id": "f5", "label": "Oświadczam, że psy nie będą wykorzystywane do polowań",
             "kind": "single_choice", "required": True, "options": ["Tak", "Nie"]}
        )  # fmt: skip
        _fields(d).append(
            {"id": "f6", "label": "Hodowanie lub utrzymywanie", "kind": "single_choice",
             "required": True, "options": ["Hodowanie", "Utrzymywanie"]}
        )  # fmt: skip

    out, warnings = normalize_draft(_make(mutate), PSY_DOC)
    assert "W17_STATEMENT_REMOVED" in _codes(warnings)
    assert "W27_VARIANT_CHOICE" not in _codes(warnings)
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3", "f4", "f6"]


def test_variant_choice_added_when_missing() -> None:
    out, warnings = normalize_draft(_make(), PSY_DOC)
    first = out.subject_pages[0].sections[0].fields[0]
    assert (first.id, first.label, first.kind) == (
        "f5",
        "Hodowanie lub utrzymywanie",
        "single_choice",
    )
    assert first.options == ["Hodowanie", "Utrzymywanie"]
    assert "W27_VARIANT_CHOICE" in _codes(warnings)


def test_variant_text_field_becomes_choice() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[0]["label"] = "Hodowanie/utrzymywanie"

    out, warnings = normalize_draft(_make(mutate), PSY_DOC)
    assert _field(out, "f1").kind == "single_choice"
    assert len(list(out.iter_fields())) == 4
    assert "W27_VARIANT_CHOICE" in _codes(warnings)


def test_purpose_field_mentioning_variants_not_converted() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d)[0]["label"] = "Cel hodowania/utrzymywania psa"

    out, _ = normalize_draft(_make(mutate), PSY_DOC)
    assert _field(out, "f1").kind == "short_text"
    assert out.subject_pages[0].sections[0].fields[0].label == "Hodowanie lub utrzymywanie"


def test_fields_copied_from_prompt_example_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _section(d, "Drzewa", "Gatunek", "Obwód pnia na wysokości 130 cm (cm)")
        _fields(d).append(
            {"id": "f9", "label": "Rodzaj", "kind": "single_choice", "required": True,
             "options": ["Drzewa", "Krzewy"]}
        )  # fmt: skip

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert _codes(warnings).count("W28_EXAMPLE_FIELD_REMOVED") == 3
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3", "f4"]


def _example_page() -> dict[str, Any]:
    """Strona, którą model oddaje, gdy przepisuje przykład z promptu zamiast czytać dokument."""

    def field(fid: str, label: str, kind: str = "short_text", **extra: Any) -> dict[str, Any]:
        return {"id": fid, "label": label, "kind": kind, "required": True, **extra}

    return {
        "title": "Informacje o drzewach",
        "sections": [
            {
                "title": "Drzewa lub krzewy do usunięcia",
                "repeating": False,
                "fields": [
                    field("e1", "Rodzaj", "single_choice", options=["Drzewa", "Krzewy"]),
                    field("e2", "Gatunek"),
                    field("e3", "Obwód pnia na wysokości 130 cm (cm)", "number"),
                ],
            },
            {
                "title": "Lokalizacja",
                "repeating": False,
                "fields": [field("e4", "Numer działki"), field("e5", "Obręb")],
            },
            {
                "title": "Usunięcie i nasadzenia",
                "repeating": False,
                "fields": [
                    field("e6", "Przyczyna usunięcia", "long_text"),
                    field("e7", "Planowany termin usunięcia", "date"),
                ],
            },
        ],
    }


def test_echoed_example_page_removed_even_when_short_labels_resemble_document() -> None:
    # „Obręb” ma 5 znaków: wystarczy „obr” z „dobrowolną”, żeby przeszło luźne dopasowanie.
    doc = _doc_blocks(
        ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki."),
        ("paragraph", "Podając numer telefonu wnioskujący wyraża dobrowolną zgodę na kontakt."),
    )

    def mutate(d: dict[str, Any]) -> None:
        _fields(d).pop()  # f4 „Obręb” nie występuje w tym dokumencie
        d["subject_pages"].append(_example_page())

    out, warnings = normalize_draft(_make(mutate), doc)
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3"]
    assert [p.title for p in out.subject_pages] == ["Informacje o budynku"]
    assert _codes(warnings).count("W28_EXAMPLE_FIELD_REMOVED") == 7


def test_echoed_example_page_removed_when_document_has_similar_fields_elsewhere() -> None:
    # Wniosek o grunt leśny: „numer działki” i „obręb” są w dokumencie, a strona to echo przykładu.
    doc = _doc_blocks(
        ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
        ("paragraph", "Wyłączenie z produkcji gruntów leśnych, drzewostan, numer działki."),
    )

    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"].append(_example_page())

    out, _ = normalize_draft(_make(mutate), doc)
    assert [f.id for _, f in out.iter_fields()] == ["f1", "f2", "f3", "f4"]


def test_page_titled_like_example_kept_when_document_is_about_trees() -> None:
    doc = _doc_blocks(
        ("paragraph", "Wniosek o usunięcie drzew lub krzewów. Rodzaj, gatunek: … Obwód pnia"),
        ("paragraph", "na wysokości 130 cm: … Nr działki: … obręb: … Przyczyna usunięcia: …"),
        ("paragraph", "Planowany termin usunięcia: …"),
    )

    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"] = [_example_page()]

    out, warnings = normalize_draft(_make(mutate), doc)
    assert "W28_EXAMPLE_FIELD_REMOVED" not in _codes(warnings)
    assert [f.id for _, f in out.iter_fields()] == ["e1", "e2", "e3", "e4", "e5", "e6", "e7"]


def test_number_inside_statement_kept() -> None:
    doc = _doc_blocks(
        ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
        ("paragraph", "Oświadczam, że średnia roczna liczba dużych jednostek owiec wynosi"),
    )

    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {"id": "f5", "label": "Średnia roczna liczba dużych jednostek owiec",
             "kind": "number", "required": True}
        )  # fmt: skip

    out, warnings = normalize_draft(_make(mutate), doc)
    assert "W17_STATEMENT_REMOVED" not in _codes(warnings)
    assert _field(out, "f5").kind == "number"


def test_example_choice_with_generic_label_removed() -> None:
    doc = _doc_blocks(
        ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
        ("paragraph", "Rodzaj dokumentu: ……… Nie dotyczy."),
    )

    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {"id": "f5", "label": "Rodzaj", "kind": "single_choice", "required": True,
             "options": ["Drzewa", "Krzewy"]}
        )  # fmt: skip
        _fields(d).append(
            {"id": "f6", "label": "Czy planowane są nasadzenia zastępcze?",
             "kind": "single_choice", "required": True, "options": ["Tak", "Nie"]}
        )  # fmt: skip

    _, warnings = normalize_draft(_make(mutate), doc)
    assert _codes(warnings).count("W28_EXAMPLE_FIELD_REMOVED") == 2


def test_computed_fields_removed_with_warning() -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["subject_pages"][0]["sections"][0]["fields"] = [
            {"id": "f1", "label": "Liczba gospodarstw", "kind": "number", "required": True},
            {"id": "f2", "label": "Stawka opłaty", "kind": "number", "required": True},
        ]

    doc = _doc_with("Liczba gospodarstw. Stawka opłaty. Do Wójt Gminy Elbląg")
    out, warnings = normalize_draft(_make(mutate), doc)
    assert [f.label for _, f in out.iter_fields()] == ["Liczba gospodarstw"]
    assert _codes(warnings) == ["W33_COMPUTED_FIELD_REMOVED"]
    assert warnings[0].message.startswith("Usunięto pole „Stawka opłaty”: ")


def test_attachments_from_document_complete_the_model() -> None:
    doc = _doc_blocks(
        ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
        ("paragraph", "Załączniki:"),
        ("paragraph", "1. Kopia aktu notarialnego"),
        ("paragraph", "2. Pełnomocnictwo - jeśli dotyczy"),
    )

    def mutate(d: dict[str, Any]) -> None:
        d["attachments"] = ["Kopia aktu notarialnego"]

    out, warnings = normalize_draft(_make(mutate), doc)
    assert out.attachments == ["Kopia aktu notarialnego", "Pełnomocnictwo - jeśli dotyczy"]
    assert _codes(warnings).count("W34_ATTACHMENT_FROM_DOCUMENT") == 1


CORRECTION_DOC = _doc_blocks(
    ("paragraph", "Wójt Gminy Elbląg. Miejscowość Ulica Numer ewidencyjny działki Obręb."),
    ("paragraph", "Cel złożenia deklaracji: złożenie deklaracji / korekta deklaracji"),
    ("paragraph", "Uzasadnienie przyczyn korekty"),
)


def test_correction_choice_with_conditional_reason_added() -> None:
    out, warnings = normalize_draft(_make(), CORRECTION_DOC)
    first, second = out.subject_pages[0].sections[0].fields[:2]
    assert (first.label, first.kind, first.options) == (
        "Cel złożenia",
        "single_choice",
        ["Złożenie deklaracji", "Korekta deklaracji"],
    )
    assert second.label == "Uzasadnienie przyczyn korekty"
    assert second.kind == "long_text"
    assert [(c.field_id, c.value) for c in second.visible_when] == [
        (first.id, "Korekta deklaracji")
    ]
    assert "W35_CORRECTION_CHOICE" in _codes(warnings)


def test_existing_purpose_choice_gets_correction_option_only() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _fields(d).append(
            {
                "id": "f5",
                "label": "Cel złożenia deklaracji",
                "kind": "single_choice",
                "required": True,
                "options": ["Złożenie deklaracji", "Zmiana danych"],
            }
        )

    doc = _doc_with("Wójt Gminy Elbląg. Cel złożenia deklaracji. Korekta deklaracji.")
    out, _ = normalize_draft(_make(mutate), doc)
    labels = [f.label for _, f in out.iter_fields()]
    assert labels.count("Cel złożenia") == 0
    assert _field(out, "f5").options[-1] == "Korekta deklaracji"
    assert "Uzasadnienie przyczyn korekty" not in labels


def test_mention_of_correction_without_purpose_heading_changes_nothing() -> None:
    def mutate(d: dict[str, Any]) -> None:
        d["attachments"] = ["Korekta deklaracji"]

    doc = _doc_with("Wójt Gminy Elbląg. Do wniosku dołączam korektę deklaracji.")
    out, warnings = normalize_draft(_make(mutate), doc)
    assert "W35_CORRECTION_CHOICE" not in _codes(warnings)
    assert "Cel złożenia" not in [f.label for _, f in out.iter_fields()]


def _consent_section(d: dict[str, Any], title: str, *fields: tuple[str, str]) -> None:
    n = sum(len(sec["fields"]) for page in d["subject_pages"] for sec in page["sections"])
    d["subject_pages"][0]["sections"].append(
        {
            "title": title,
            "repeating": False,
            "fields": [
                {"id": f"f{n + i}", "label": label, "kind": kind, "required": kind != "info"}
                for i, (kind, label) in enumerate(fields, 1)
            ],
        }
    )


def test_data_consent_section_moves_to_consent_section() -> None:
    minor = (
        "Wyrażam zgodę na przetwarzanie danych osobowych mojego dziecka/podopiecznego "
        "zawartych we wniosku"
    )

    def mutate(d: dict[str, Any]) -> None:
        _consent_section(
            d,
            "Zgoda podopiecznego pełnoletniego",
            ("short_text", "Imię i nazwisko podopiecznego"),
            (
                "info",
                "1) Wyrażam zgodę na przetwarzanie moich danych osobowych zawartych we wniosku",
            ),
            ("date", "Data"),
        )
        _consent_section(
            d,
            "Zgoda w imieniu podopiecznego nieletniego",
            ("short_text", "Imię i nazwisko podopiecznego"),
            ("info", minor),
            ("date", "Data"),
        )
        _consent_section(
            d, "Zgoda na przetwarzanie danych", ("info", "Zgoda na przetwarzanie danych osobowych")
        )

    out, warnings = normalize_draft(_make(mutate), DOC)
    titles = [s.title for p in out.subject_pages for s in p.sections]
    assert not any(t.startswith("Zgoda") for t in titles)
    # Zgodę na własne dane pokrywa standardowa zgoda RODO; zgoda za dziecko trafia do zgód.
    assert out.statements == [minor]
    assert _codes(warnings).count("W36_DATA_CONSENT_MOVED") == 3


def test_data_consent_section_with_other_data_kept() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _consent_section(
            d,
            "Zgoda na przetwarzanie danych",
            ("info", "Wyrażam zgodę na przetwarzanie danych osobowych dziecka"),
            ("single_choice", "Klasa"),
        )
        d["subject_pages"][0]["sections"][-1]["fields"][1]["options"] = ["1", "2"]

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert out.subject_pages[0].sections[-1].title == "Zgoda na przetwarzanie danych"
    assert "W36_DATA_CONSENT_MOVED" not in _codes(warnings)


def test_statement_section_left_with_data_is_retitled() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _consent_section(
            d,
            "Oświadczenia",
            ("number", "Opłata skarbowa"),
            ("single_choice", "Oświadczam, że psy nie będą wykorzystywane do polowań"),
        )
        d["subject_pages"][0]["sections"][-1]["fields"][1]["options"] = ["Tak", "Nie"]

    out, warnings = normalize_draft(_make(mutate), PSY_DOC)
    section = out.subject_pages[0].sections[-1]
    assert [f.label for f in section.fields] == ["Opłata skarbowa"]
    assert section.title == "Opłata skarbowa"
    assert "W37_SECTION_RETITLED" in _codes(warnings)


def test_statement_section_title_kept_when_nothing_was_removed() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _consent_section(d, "Oświadczenia", ("number", "Liczba psów"))

    out, warnings = normalize_draft(_make(mutate), PSY_DOC)
    assert out.subject_pages[0].sections[-1].title == "Oświadczenia"
    assert "W37_SECTION_RETITLED" not in _codes(warnings)


def test_data_section_with_consent_block_kept() -> None:
    def mutate(d: dict[str, Any]) -> None:
        _consent_section(
            d,
            "Dane kandydata",
            ("short_text", "Imię i nazwisko kandydata"),
            ("info", "Zgoda na przetwarzanie danych osobowych"),
        )

    out, warnings = normalize_draft(_make(mutate), DOC)
    assert out.subject_pages[0].sections[-1].title == "Dane kandydata"
    assert "W36_DATA_CONSENT_MOVED" not in _codes(warnings)
