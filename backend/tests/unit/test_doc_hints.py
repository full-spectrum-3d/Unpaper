from app.models.document import DocumentModel
from app.pipeline.doc_hints import annotate_choices


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


def _p(text: str) -> tuple[str, str]:
    return ("paragraph", text)


def _lines(*blocks: tuple[str, str]) -> list[str]:
    return annotate_choices(_doc(*blocks)).to_prompt_text().splitlines()[1:]


def test_list_after_request_with_colon_becomes_options() -> None:
    assert _lines(
        _p("Proszę o wydanie zaświadczenia o:*"),
        _p("ilości posiadanych użytków rolnych"),
        _p("okresie posiadania gospodarstwa rolnego"),
        _p("inne ……………"),
        ("input_placeholder", "……………"),
        _p("Zaświadczenie potrzebne jest celem przedłożenia w ………"),
    ) == [
        "Proszę o wydanie zaświadczenia o:*",
        "[OPCJA] ilości posiadanych użytków rolnych",
        "[OPCJA] okresie posiadania gospodarstwa rolnego",
        "[OPCJA] inne [POLE]",
        "[POLE]",
        "Zaświadczenie potrzebne jest celem przedłożenia w [POLE]",
    ]


def test_mark_with_x_list_stops_at_conditional_note() -> None:
    assert _lines(
        _p("5. Sposób zwrotu opłaty (postaw „x” w wybranym polu)"),
        _p("Gotówką w kasie organu"),
        _p("Przelewem na rachunek w banku"),
        _p("Jeśli wybierzesz tę formę, wpisz poniżej nr rachunku"),
        _p("Nr rachunku"),
    )[1:] == [
        "[OPCJA] Gotówką w kasie organu",
        "[OPCJA] Przelewem na rachunek w banku",
        "Jeśli wybierzesz tę formę, wpisz poniżej nr rachunku",
        "Nr rachunku",
    ]


def test_inline_numbered_options_split() -> None:
    assert _lines(
        _p("1. Składający deklarację (zaznaczyć właściwą kratkę)"),
        _p("1. właściciel 2. najemca/dzierżawca 3. wspólnota mieszkaniowa"),
    )[1:] == ["[OPCJA] właściciel", "[OPCJA] najemca/dzierżawca", "[OPCJA] wspólnota mieszkaniowa"]


def test_yes_no_and_box_glyphs() -> None:
    lines = _lines(_p("1. Załącznik A TAK NIE"), ("heading", "TAK NIE"), _p("Płeć: ❑ pies ❑ suka"))
    assert lines == [
        "1. Załącznik A", "[OPCJA] Tak", "[OPCJA] Nie", "[OPCJA] Tak", "[OPCJA] Nie",
        "Płeć:", "[OPCJA] pies", "[OPCJA] suka",
    ]  # fmt: skip


def test_short_list_after_heading_with_colon() -> None:
    lines = _lines(("heading", "Dyscypliny sportowe:"), _p("hokej"), _p("karate"), _p("zapasy"))
    assert lines[1:] == ["[OPCJA] hokej", "[OPCJA] karate", "[OPCJA] zapasy"]


def test_numbered_list_after_weak_cue_without_colon() -> None:
    lines = _lines(
        _p("33. Rodzaj nieruchomości"),
        _p("1. Zabudowana jednorodzinna"),
        _p("2. Zabudowana wielolokalowa"),
    )
    assert lines[1:] == ["[OPCJA] Zabudowana jednorodzinna", "[OPCJA] Zabudowana wielolokalowa"]


def _unchanged(*blocks: tuple[str, str]) -> None:
    doc = _doc(*blocks)
    assert annotate_choices(doc).to_prompt_text() == doc.to_prompt_text()


def test_statements_attachments_and_plain_lists_unchanged() -> None:
    _unchanged(
        _p("Jednocześnie oświadczam, że:"),
        _p("zapoznałem się z regulaminem"),
        _p("odpowiadam za porządek"),
    )
    _unchanged(_p("Załączniki do wniosku:"), _p("plan sytuacyjny"), _p("harmonogram robót"))
    _unchanged(
        _p("B.2 Dane współmałżonka (wypełnić w przypadku zaznaczenia kratki)"),
        _p("5. Nazwisko, imię"),
        _p("6. Adres zamieszkania"),
    )
    _unchanged(
        _p("1. Powierzchnia pasa drogowego potrzebna do zajęcia:"),
        _p("a/ jezdnia (przy zajęciu do 20% szerokości)"),
        _p("b/ chodnik"),
    )
    _unchanged(
        _p("Kwotę nadpłaty proszę:"),
        _p("1) zaliczyć na poczet zobowiązania ………"),
        ("input_placeholder", "……"),
        _p("2) zwrócić przelewem"),
    )


def test_existing_options_kept() -> None:
    _unchanged(
        _p("Korespondencja (wybierz sposób)"),
        ("checkbox_option", "Poczta"),
        ("checkbox_option", "ePUAP"),
    )


def test_block_ids_stay_unique() -> None:
    doc = annotate_choices(_doc(_p("Płeć: ❑ pies ❑ suka"), _p("Wybierz:")))
    ids = [b.id for b in doc.iter_blocks()]
    assert len(ids) == len(set(ids))


def test_ocr_brackets_as_boxes() -> None:
    assert _lines(_p("Czy planowane są nasadzenia? [ ] tak [] nie")) == [
        "Czy planowane są nasadzenia?",
        "[OPCJA] tak",
        "[OPCJA] nie",
    ]


def test_short_list_of_field_labels_is_not_a_choice() -> None:
    _unchanged(_p("Wnioskodawca:"), _p("Imię i nazwisko"), _p("Adres"), _p("Nr telefonu"))
