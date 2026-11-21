import itertools
import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest

import app.pipeline.build as build_module
from app.models.draft import (
    ApplicantKind,
    Condition,
    DraftField,
    DraftPage,
    DraftSection,
    FormDraft,
)
from app.models.form import BASE_FIELD_KEYS
from app.pipeline.build import BuildOptions, build_fallback, build_form
from app.pipeline.issues import IssueCode
from app.pipeline.verify import verify_form


def counter() -> Callable[[], str]:
    numbers = itertools.count(1)
    return lambda: f"id{next(numbers)}"


def opts(**kwargs: Any) -> BuildOptions:
    return BuildOptions(id_factory=counter(), **kwargs)


def walk_fields(form: dict[str, Any]) -> Iterator[dict[str, Any]]:
    def rec(field: dict[str, Any]) -> Iterator[dict[str, Any]]:
        yield field
        for child in field["repeatingSectionGrid"]:
            yield from rec(child["field"])

    for tab in form["tabs"]:
        for question in tab["questions"]:
            yield from rec(question["field"])


def find(form: dict[str, Any], tech_name: str) -> dict[str, Any]:
    return next(f for f in walk_fields(form) if f["techName"] == tech_name)


def build_json(draft: FormDraft, options: BuildOptions | None = None) -> dict[str, Any]:
    return build_form(draft, options or opts()).form.to_import_json()


def page(title: str, *sections: DraftSection) -> DraftPage:
    return DraftPage(title=title, sections=list(sections))


def section(title: str, *fields: DraftField, repeating: bool = False) -> DraftSection:
    return DraftSection(title=title, repeating=repeating, fields=list(fields))


def fld(id: str, label: str, kind: Any = "short_text", **kwargs: Any) -> DraftField:
    kwargs.setdefault("required", False)
    return DraftField(id=id, label=label, kind=kind, **kwargs)


def make_draft(*pages: DraftPage, **kwargs: Any) -> FormDraft:
    data: dict[str, Any] = {
        "title": "Wniosek o X",
        "authority_kind": "URZAD",
        "authority_name": "Urząd Gminy",
        "applicant_kinds": ["SELF"],
        "subject_pages": list(pages),
    }
    data.update(kwargs)
    return FormDraft.model_validate(data)


def broken_draft(*fields: DraftField) -> FormDraft:
    """Szkic z pominiętą walidacją: odwołania, które model normalnie odrzuca."""
    return FormDraft.model_construct(
        title="Wniosek o X",
        authority_kind="URZAD",
        authority_name="Urząd Gminy",
        applicant_kinds=["SELF"],
        attachments=[],
        statements=[],
        subject_pages=[page("Przedmiot", section("Sekcja", *fields))],
    )


def test_minimal_draft() -> None:
    form = build_json(make_draft())
    assert [t["title"] for t in form["tabs"]] == ["Dane", "Kontakt i zgody", "Strona końcowa"]
    assert [t["type"] for t in form["tabs"]] == ["MAIN", "MAIN", "FINISH"]
    assert not any(f["techName"] == "podmiot_wniosku" for f in walk_fields(form))
    assert verify_form(form, autofix=False).valid


def test_unknown_condition_target_is_dropped_with_warning() -> None:
    cond = Condition(field_id="f9", op="equals", value="Tak")
    result = build_form(broken_draft(fld("f1", "Pole", visible_when=[cond])), opts())
    assert [w.path for w in result.warnings if w.code == IssueCode.W03_CONDITION_UNRESOLVED] == [
        "p1.s1.f1"
    ]
    assert find(result.form.to_import_json(), "pole")["states"] == []


def test_condition_on_non_choice_target_is_dropped_with_warning() -> None:
    cond = Condition(field_id="f1", op="equals", value="Tak")
    draft = broken_draft(fld("f1", "Tekst"), fld("f2", "Pole", visible_when=[cond]))
    result = build_form(draft, opts())
    assert [w.path for w in result.warnings if w.code == IssueCode.W03_CONDITION_UNRESOLVED] == [
        "p1.s1.f2"
    ]
    assert find(result.form.to_import_json(), "pole")["states"] == []


def test_condition_on_itself_is_dropped_with_warning() -> None:
    cond = Condition(field_id="f1", op="equals", value="Tak")
    result = build_form(
        broken_draft(
            fld("f1", "Pole", "single_choice", options=["Tak", "Nie"], visible_when=[cond])
        ),
        opts(),
    )
    assert [w.path for w in result.warnings if w.code == IssueCode.W03_CONDITION_UNRESOLVED] == [
        "p1.s1.f1"
    ]
    assert find(result.form.to_import_json(), "pole")["states"] == []


def test_choice_without_options_makes_condition_unresolved() -> None:
    # model_construct: draft_normalize zamienia taki wybór na short_text, więc cel nie jest wyborem
    choice = fld("f1", "Wybór", "single_choice")
    cond = Condition(field_id="f1", op="equals", value="Tak")
    result = build_form(broken_draft(choice, fld("f2", "Pole", visible_when=[cond])), opts())
    codes = [w.code for w in result.warnings]
    assert IssueCode.W07_CHOICE_OPTIONS in codes
    assert IssueCode.W03_CONDITION_UNRESOLVED in codes


def test_duplicate_labels_resolve_by_id() -> None:
    def part(title: str, suffix: str) -> DraftSection:
        return section(
            title,
            fld(f"c{suffix}", "Brak nazwy ulicy", "multi_choice", options=["Brak nazwy ulicy"]),
            fld(
                f"u{suffix}",
                "Ulica",
                visible_when=[
                    Condition(field_id=f"c{suffix}", op="equals", value="Brak nazwy ulicy")
                ],
            ),
        )

    draft = make_draft(page("Pierwsza", part("A", "1")), page("Druga", part("B", "2")))
    form = build_json(draft)
    tabs = {t["title"]: t for t in form["tabs"]}
    first, second = (
        next(
            f
            for q in tabs[name]["questions"]
            for c in q["field"]["repeatingSectionGrid"]
            if (f := c["field"])["title"] == "Ulica"
        )
        for name in ("Pierwsza", "Druga")
    )
    assert [s["type"] for s in first["states"]] == ["SHOW"]
    assert "'brak_nazwy_ulicy' in field.techName" in first["states"][0]["query"]
    assert "'Pierwsza' in title" in first["states"][0]["query"]
    assert "'brak_nazwy_ulicy_2' in field.techName" in second["states"][0]["query"]
    assert "'Druga' in title" in second["states"][0]["query"]


def test_conditions_by_id_support_not_equals_and_and() -> None:
    draft = make_draft(
        page(
            "Przedmiot",
            section(
                "Sekcja",
                fld("f1", "Rodzaj", "single_choice", options=["A", "B"]),
                fld("f2", "Drugi", "single_choice", options=["X", "Y"]),
                fld(
                    "f3",
                    "Zależne",
                    visible_when=[
                        Condition(field_id="f1", op="not_equals", value="A"),
                        Condition(field_id="f2", op="equals", value="Y"),
                    ],
                ),
            ),
        )
    )
    states = find(build_json(draft), "zalezne")["states"]
    assert [s["type"] for s in states] == ["SHOW"]
    query = states[0]["query"]
    assert "'rodzaj' in field.techName" in query
    assert "'drugi' in field.techName" in query
    assert "not(" in query.replace(" ", "")
    assert " and " in query


def test_label_semantics_drive_dictionaries_and_validators() -> None:
    draft = make_draft(
        page(
            "Przedmiot",
            section(
                "Sekcja",
                fld("f1", "Kraj urodzenia"),
                fld("f2", "Numer kierunkowy"),
                fld("f3", "Numer NIP", required=True),
            ),
        )
    )
    form = build_json(draft)
    assert find(form, "kraj_urodzenia")["dictionaryName"] == "Kraje"
    assert find(form, "numer_kierunkowy")["dictionaryName"] == "NUMERY_KIERUNKOWE"
    nip = find(form, "numer_nip")
    assert nip["validation"] == ["REQUIRED", "NIP"]
    assert "dictionaryName" not in nip


def test_contact_section_has_phone_prefix_before_phone() -> None:
    form = build_json(make_draft(page("Przedmiot", section("Sekcja", fld("f1", "Opis")))))
    contact = find(form, "dane_do_kontaktu")
    names = [
        g["field"]["techName"]
        for g in sorted(contact["repeatingSectionGrid"], key=lambda g: g["y"])
    ]
    assert names[:2] == ["numer_kierunkowy", "numer_telefonu"]
    prefix = find(form, "numer_kierunkowy")
    assert prefix["type"] == "SELECT"
    assert prefix["dictionaryName"] == "NUMERY_KIERUNKOWE"
    assert prefix["options"] == []
    assert prefix["defaultValue"] == ["+48"]
    assert prefix["searchEnabled"] is True
    assert prefix["validation"] == []


def test_address_unit_labels_get_dictionaries() -> None:
    draft = make_draft(
        page(
            "Przedmiot",
            section("Położenie", fld("f1", "Gmina"), fld("f2", "Miejscowość")),
        )
    )
    form = build_json(draft)
    assert find(form, "gmina")["dictionaryName"] == "Gmina"
    locality = find(form, "miejscowosc")
    assert locality["type"] == "TEXT_FIELD"
    assert "dictionaryName" not in locality


def test_build_result_has_dictionary_proposals() -> None:
    draft = make_draft(page("Przedmiot", section("Nadpłata", fld("f1", "Nazwa podatku"))))
    result = build_form(draft, opts())
    assert [p.name for p in result.dictionary_proposals] == ["RODZAJE_PODATKOW_LOKALNYCH"]
    assert result.dictionary_proposals[0].used_by == ("nazwa_podatku",)
    assert find(result.form.to_import_json(), "nazwa_podatku")["type"] == "TEXT_FIELD"


@pytest.mark.parametrize("kind", ["single_choice", "multi_choice"])
def test_choice_labelled_country_keeps_options_and_conditions(kind: str) -> None:
    draft = make_draft(
        page(
            "Przedmiot",
            section(
                "Sekcja",
                fld("f1", "Państwo", kind, options=["Polska", "Niemcy"]),
                fld(
                    "f2",
                    "Powód",
                    visible_when=[Condition(field_id="f1", op="equals", value="Niemcy")],
                ),
            ),
        )
    )
    form = build_json(draft)
    country = find(form, "panstwo")
    assert "dictionaryName" not in country
    assert [o["name"] for o in country["options"]] == ["Polska", "Niemcy"]
    assert [s["type"] for s in find(form, "powod")["states"]] == ["SHOW"]


def test_one_bad_condition_drops_whole_list_with_one_warning() -> None:
    good = Condition(field_id="f1", op="equals", value="A")
    bad = Condition(field_id="f9", op="equals", value="A")
    choice = fld("f1", "Wybór", "single_choice", options=["A", "B"])
    result = build_form(broken_draft(choice, fld("f2", "Pole", visible_when=[good, bad])), opts())
    w03 = [w for w in result.warnings if w.code == IssueCode.W03_CONDITION_UNRESOLVED]
    assert len(w03) == 1
    assert "f9" in w03[0].message
    assert "f1" not in w03[0].message
    assert find(result.form.to_import_json(), "pole")["states"] == []


def test_attachment_duplicate_skipped() -> None:
    draft = make_draft(
        page("Przedmiot", section("Sekcja", fld("f1", "Kopia  umowy", "file"))),
        attachments=["kopia umowy", "Kopia umowy"],
    )
    result = build_form(draft, opts())
    assert IssueCode.W10_ATTACHMENT_DUPLICATE in [w.code for w in result.warnings]
    assert not any(f["techName"] == "zalaczniki" for f in walk_fields(result.form.to_import_json()))


def test_fallback() -> None:
    result = build_fallback("Wniosek o Y", options=opts())
    assert result.warnings[0].code == IssueCode.W01_LLM_FALLBACK
    assert verify_form(result.form.to_import_json(), autofix=False).valid
    assert result.form.title == "Wniosek o Y"


def test_fallback_defaults() -> None:
    result = build_fallback(options=opts())
    assert result.form.title == "Wniosek"
    assert verify_form(result.form.to_import_json(), autofix=False).valid


def test_deterministic() -> None:
    a = build_json(make_draft(), opts())
    b = build_json(make_draft(), opts())
    assert json.dumps(a) == json.dumps(b)


def test_form_definition_matches_serialized_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []
    original = build_module.to_form_definition

    def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = original(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(build_module, "to_form_definition", spy)
    draft = make_draft(
        page(
            "Przedmiot",
            section(
                "Sekcja",
                fld("f1", "Kraj"),
                fld("f2", "Wybór", "single_choice", options=["A", "B"]),
                fld("f3", "Plik", "file"),
            ),
        ),
        applicant_kinds=list(ApplicantKind.__args__),
        statements=["Oświadczam, że dane są prawdziwe."],
    )
    result = build_form(draft, opts())
    assert len(captured) == 1
    assert result.form.to_import_json() == captured[0]
    # także kolejność kluczy (klucze bazowe pola, potem dodatkowe)
    assert json.dumps(result.form.to_import_json()) == json.dumps(captured[0])


def test_layout() -> None:
    form = build_json(make_draft())
    questions = form["tabs"][0]["questions"]
    expected_y = 0
    for question in questions:
        assert question["y"] == expected_y
        assert question["field"]["questionOrder"] == question["y"]
        assert (question["x"], question["cols"]) == (0, 3)
        fields = question["field"]["repeatingSectionGrid"]
        assert question["rows"] == len(fields) + 1
        for index, child in enumerate(fields):
            assert (child["y"], child["rows"]) == (index, 1)
            assert child["field"]["questionOrder"] == index
        expected_y += question["rows"]


def test_every_field_has_base_keys() -> None:
    form = build_json(make_draft(page("P", section("S", fld("f1", "Pole")))))
    for field in walk_fields(form):
        assert tuple(field)[: len(BASE_FIELD_KEYS)] == BASE_FIELD_KEYS
    assert find(form, "pole")["tooltipMessage"] == ""


def test_info_field_is_text_block_with_label() -> None:
    form = build_json(make_draft(page("P", section("S", fld("f1", "Uwaga <b>", "info")))))
    block = next(
        f for f in walk_fields(form) if f["type"] == "TEXT_BLOCK" and "Uwaga" in f["description"]
    )
    assert "<p>Uwaga &lt;b&gt;</p>" in block["description"]


def test_page_split() -> None:
    sections = [section(f"S{i}", fld(f"f{i}", f"Pole {i}")) for i in range(10)]
    form = build_json(make_draft(page("X", *sections)), opts(max_sections_per_page=4))
    assert [t["title"] for t in form["tabs"]][1:4] == ["X", "X (cd.)", "X (cd. 2)"]
    links = form["flow"]["links"]
    assert len(links) == len(form["tabs"]) - 1
    assert links[0]["source"] == form["tabs"][0]["id"]
    assert links[0]["target"] == form["tabs"][1]["id"]


_KINDS: tuple[ApplicantKind, ...] = ("SELF", "OTHER_PERSON", "LEGAL_ENTITY")
_KIND_SUBSETS = [
    list(combo)
    for size in range(1, len(_KINDS) + 1)
    for combo in itertools.combinations(_KINDS, size)
]


@pytest.mark.parametrize("kinds", _KIND_SUBSETS, ids=lambda k: "+".join(k))
def test_every_applicant_kind_subset_builds_valid_form(kinds: list[ApplicantKind]) -> None:
    form = build_json(make_draft(applicant_kinds=kinds))
    result = verify_form(form, autofix=False)
    assert result.valid, result.errors


def test_other_person_alone_is_normalized_with_self() -> None:
    form = build_json(make_draft(applicant_kinds=["OTHER_PERSON"]))
    radio = find(form, "wybierz_w_czyim_imieniu_wnioskujesz")
    assert [o["name"] for o in radio["options"]] == ["Swoim", "Innej osoby"]


def test_applicant_gets_single_home_address() -> None:
    form = build_json(make_draft(applicant_kinds=["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]))
    titles = [f["title"] for f in walk_fields(form) if f["type"] == "SECTION"]
    assert titles.count("Adres zamieszkania") == 1
    assert "Adres siedziby" in titles
    assert "Adres zamieszkania innej osoby" in titles
    assert not any("zameldowania" in t or "korespondencyjny" in t for t in titles)


def test_finish_page_has_only_preview() -> None:
    form = build_json(make_draft())
    finish = form["tabs"][-1]
    assert [q["field"]["techName"] for q in finish["questions"]] == [
        "podglad_uzupelnionego_wniosku"
    ]


def test_legal_entity_alone_has_only_role_radio() -> None:
    form = build_json(make_draft(applicant_kinds=["LEGAL_ENTITY"]))
    names = {f["techName"] for f in walk_fields(form)}
    assert "wybierz_w_czyim_imieniu_wnioskujesz" not in names
    role = find(form, "wybierz_jako_kto_wnioskujesz")
    assert role["validation"] == ["REQUIRED"]
    assert not role["states"]
    for tech in ("dane_podmiotu", "adres_siedziby"):
        assert not find(form, tech)["states"], tech
    for tech in (
        "potwierdzenie_ze_jestes_reprezentantem",
        "pelnomocnictwo",
        "oplata_skarbowa_pelnomocnictwo_2",
    ):
        queries = [s["query"] for s in find(form, tech)["states"]]
        assert queries, tech
        assert all("w_czyim_imieniu" not in q for q in queries), tech
        assert all("jako_kto" in q for q in queries), tech


def test_reference_into_repeating_section_from_outside_is_dropped() -> None:
    draft = make_draft(
        page(
            "Przedmiot",
            section(
                "Powtarzalna",
                fld("f1", "Wnętrze", "single_choice", options=["Tak", "Nie"]),
                repeating=True,
            ),
            section(
                "Zwykła",
                fld(
                    "f2",
                    "Na zewnątrz",
                    visible_when=[Condition(field_id="f1", op="equals", value="Tak")],
                ),
            ),
        )
    )
    result = build_form(draft, opts())
    assert find(result.form.to_import_json(), "na_zewnatrz")["states"] == []
    assert IssueCode.W06_STATE_REMOVED in [w.code for w in result.warnings]
