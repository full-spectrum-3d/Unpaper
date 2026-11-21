"""Sekcje predefiniowane z szablonów (spec §8.2)."""

import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any, Literal, Self

from app.core.config import Settings
from app.models.draft import ApplicantKind, FormDraft
from app.models.form import FieldType, Validator
from app.pipeline.build.fields import normalize_title, slugify
from app.pipeline.build.file_hints import file_constraints_html
from app.pipeline.build.html import external_link, paragraphs
from app.pipeline.build.ir import AllOf, AnyOf, Condition, Consent, Eq, FieldNode, Not, SectionNode

SUBJECT_CHOICE_KEY = "podmiot_wniosku.w_czyim_imieniu"
ROLE_CHOICE_KEY = "podmiot_wniosku.jako_kto"

APPLICANT_OPTIONS: dict[ApplicantKind, str] = {
    "SELF": "Swoim",
    "OTHER_PERSON": "Innej osoby",
    "LEGAL_ENTITY": "Osoby prawnej lub jednostki organizacyjnej",
}

_ROLE_REPRESENTATIVE = "Reprezentant"
_ROLE_ATTORNEY = "Pełnomocnik"
_PREVIEW_SIGNED = (
    "Zanim przejdziesz do wyboru sposobu podpisu, sprawdź dane na podglądzie. "
    "Jeśli zobaczysz błędy, wróć do edycji."
)
_PREVIEW_UNSIGNED = (
    "Zanim wyślesz formularz, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji."
)


def _new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class BuildOptions:
    identity_source: Literal["MLPZ", "PESEL"] = "MLPZ"
    finish_page_style: Literal["sample", "info_section"] = "sample"
    max_sections_per_page: int = 8
    rodo_clause_url: str | None = None
    signed: bool = True
    id_factory: Callable[[], str] = _new_uuid

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            identity_source=settings.initial_data_identity_source,
            finish_page_style=settings.finish_page_style,
            max_sections_per_page=settings.max_sections_per_page,
            rodo_clause_url=settings.rodo_clause_url,
        )


@cache
def load_template(name: str) -> dict[str, Any]:
    text = (files("app.resources") / "templates" / name).read_text(encoding="utf-8")
    template: dict[str, Any] = json.loads(text)
    return template


def _substitute(text: str, values: Mapping[str, str], *, html: bool) -> str:
    for name, value in values.items():
        text = text.replace(f"{{{name}}}", escape(value) if html else value)
    return text


def _condition(spec: dict[str, Any], key: str) -> Condition:
    if "eq" in spec:
        ref, value = spec["eq"]
        return Eq(ref if "." in ref else f"{key}.{ref}", value)
    if "not" in spec:
        return Not(_condition(spec["not"], key))
    if "all" in spec:
        return AllOf(tuple(_condition(item, key) for item in spec["all"]))
    return AnyOf(tuple(_condition(item, key) for item in spec["any"]))


def _field(raw: dict[str, Any], key: str, values: Mapping[str, str], source: str) -> FieldNode:
    def plain(text: str) -> str:
        return _substitute(text, values, html=False)

    default = raw.get("defaultValue")
    if isinstance(default, str):
        default = plain(default)
    initial = raw.get("initialData")
    if initial is not None:
        initial = plain(initial).replace("IDENTITY.", f"{source}.", 1)
    node = FieldNode(
        key=f"{key}.{plain(raw['key'])}",
        type=FieldType(raw["type"]),
        title=plain(raw["title"]),
        tech_name=plain(raw["techName"]),
        description_html=_substitute(raw.get("descriptionHtml", ""), values, html=True),
        tooltip=plain(raw.get("tooltipMessage", "")),
        options=[plain(option) for option in raw.get("options", [])],
        validation=[Validator(v) for v in raw.get("validation", [])],
        read_only=raw.get("readOnly", False),
        dictionary_name=raw.get("dictionaryName"),
        search_enabled=raw.get("searchEnabled"),
        multi_level_tree=raw.get("multiLevelTree"),
        default_value=default,
        initial_data=initial,
    )
    if "showWhen" in raw:
        node.show_when = _condition(raw["showWhen"], key)
    if "readOnlyWhen" in raw:
        node.read_only_when = _condition(raw["readOnlyWhen"], key)
    return node


def instantiate(
    template: dict[str, Any],
    *,
    key: str,
    suffix: str = "",
    params: Mapping[str, str] = {},
    initial_data: bool = True,
    identity_source: str = "MLPZ",
) -> SectionNode:
    values = {**params, "sfx": suffix}
    fields = [_field(raw, key, values, identity_source) for raw in template["fields"]]
    if not initial_data:
        for node in fields:
            node.initial_data = None
    return SectionNode(
        key=key,
        type=FieldType.SECTION,
        title=_substitute(template["title"], values, html=False),
        tech_name=_substitute(template["techName"], values, html=False),
        description_html=_substitute(template.get("descriptionHtml", ""), values, html=True),
        fields=fields,
    )


def _address(
    title: str, tech_name: str, suffix: str, options: BuildOptions, *, initial_data: bool
) -> SectionNode:
    return instantiate(
        load_template("address.json"),
        key=tech_name,
        suffix=suffix,
        params={"title": title, "section_tech_name": tech_name},
        initial_data=initial_data,
        identity_source=options.identity_source,
    )


def _authority(draft: FormDraft) -> SectionNode:
    if draft.authority_kind == "ORGAN":
        title, tech = (
            "Organ, do którego jest składany wniosek",
            "organ_do_ktorego_jest_skladany_wniosek",
        )
        label, field_tech = "Nazwa organu", "nazwa_organu"
    else:
        title, tech = (
            "Urząd, do którego jest składany wniosek",
            "urzad_do_ktorego_jest_skladany_wniosek",
        )
        label, field_tech = "Nazwa urzędu", "nazwa_urzedu"
    section = instantiate(
        load_template("authority.json"),
        key=tech,
        params={
            "title": title,
            "section_tech_name": tech,
            "label": label,
            "field_tech_name": field_tech,
        },
    )
    section.fields[0].default_value = draft.authority_name
    return section


def _subject(kinds: set[ApplicantKind]) -> SectionNode:
    section = instantiate(load_template("applicant_subject.json"), key="podmiot_wniosku")
    ordered = [kind for kind in APPLICANT_OPTIONS if kind in kinds]
    section.fields[0].options = [APPLICANT_OPTIONS[kind] for kind in ordered]
    if "LEGAL_ENTITY" not in kinds:
        section.fields.pop()
    elif kinds == {"LEGAL_ENTITY"}:
        # Jedyny rodzaj wnioskodawcy: pytanie „w czyim imieniu” zbędne, rola widoczna zawsze.
        section.fields.pop(0)
        section.fields[0].show_when = None
    return section


def applicant_page_sections(draft: FormDraft, options: BuildOptions) -> list[SectionNode]:
    kinds = set(draft.applicant_kinds)
    legal = "LEGAL_ENTITY" in kinds
    other = "OTHER_PERSON" in kinds
    is_legal = Eq(SUBJECT_CHOICE_KEY, APPLICANT_OPTIONS["LEGAL_ENTITY"])
    is_other = Eq(SUBJECT_CHOICE_KEY, APPLICANT_OPTIONS["OTHER_PERSON"])
    only_legal = kinds == {"LEGAL_ENTITY"}
    is_attorney = Eq(ROLE_CHOICE_KEY, _ROLE_ATTORNEY)
    legal_attorney = is_attorney if only_legal else AllOf((is_legal, is_attorney))
    form_title = {"form_title": normalize_title(draft.title)[0]}

    sections = [_authority(draft)]
    if kinds != {"SELF"}:
        sections.append(_subject(kinds))
    sections.append(
        instantiate(
            load_template("your_data.json"),
            key="twoje_dane",
            identity_source=options.identity_source,
        )
    )
    sections.append(
        _address("Adres zamieszkania", "adres_zamieszkania", "", options, initial_data=True)
    )

    def add(name: str, key: str, show: Condition | None, **kwargs: Any) -> None:
        section = instantiate(load_template(name), key=key, **kwargs)
        section.show_when = show
        sections.append(section)

    if legal:
        legal_show = None if only_legal else is_legal
        is_representative = Eq(ROLE_CHOICE_KEY, _ROLE_REPRESENTATIVE)
        add("entity.json", "dane_podmiotu", legal_show)
        seat = _address(
            "Adres siedziby", "adres_siedziby", "_siedziba", options, initial_data=False
        )
        seat.show_when = legal_show
        sections.append(seat)
        add(
            "representative.json",
            "potwierdzenie_ze_jestes_reprezentantem",
            is_representative if only_legal else AllOf((is_legal, is_representative)),
        )
    if other:
        add("other_person.json", "dane_innej_osoby", is_other)
        person = _address(
            "Adres zamieszkania innej osoby",
            "adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem",
            "_inna_osoba",
            options,
            initial_data=False,
        )
        person.show_when = is_other
        sections.append(person)
    if other or legal:
        branches: list[Condition] = []
        if other:
            branches.append(is_other)
        if legal:
            branches.append(legal_attorney)
        add(
            "power_of_attorney.json",
            "pelnomocnictwo",
            branches[0] if len(branches) == 1 else AnyOf(tuple(branches)),
        )
    if other:
        add("stamp_duty_v1.json", "oplata_skarbowa_pelnomocnictwo_1", is_other, params=form_title)
    if legal:
        add(
            "stamp_duty_v2.json",
            "oplata_skarbowa_pelnomocnictwo_2",
            legal_attorney,
            params=form_title,
        )
    return sections


def _consent_section(draft: FormDraft, options: BuildOptions) -> SectionNode:
    if options.rodo_clause_url:
        clause = external_link(options.rodo_clause_url, "klauzulą informacyjną")
    else:
        clause = "klauzulą informacyjną"
    consents = [
        Consent(
            f"<p>Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z {clause}</p>",
            True,
        )
    ]
    consents += [Consent(paragraphs(text), True) for text in draft.statements]
    block = FieldNode(
        key="zgody.zgoda",
        type=FieldType.CONSENT_SECTION,
        title="",
        tech_name="zgoda",
        consents=consents,
        select_all_enabled=True if len(consents) > 1 else None,
    )
    if draft.statements:
        title, tech = "Zgody i oświadczenia", "zgody_i_oswiadczenia"
    else:
        title, tech = "Zgoda", "zgoda_wyrazenie"
    return SectionNode(
        key="zgody", type=FieldType.SECTION, title=title, tech_name=tech, fields=[block]
    )


def contact_page_sections(
    draft: FormDraft, options: BuildOptions, extra_attachments: list[str]
) -> list[SectionNode]:
    sections = [instantiate(load_template("contact.json"), key="dane_do_kontaktu")]
    if extra_attachments:
        description = file_constraints_html()
        fields = [
            FieldNode(
                key=f"zalaczniki.zalacznik_{index}",
                type=FieldType.FILE_UPLOADER,
                title=name,
                tech_name=slugify(name),
                description_html=description,
                validation=[Validator.REQUIRED],
            )
            for index, name in enumerate(extra_attachments, start=1)
        ]
        sections.append(
            SectionNode(
                key="zalaczniki",
                type=FieldType.SECTION,
                title="Załączniki",
                tech_name="zalaczniki",
                fields=fields,
            )
        )
    sections.append(_consent_section(draft, options))
    return sections


def finish_page_sections(draft: FormDraft, options: BuildOptions) -> list[SectionNode]:
    text = _PREVIEW_SIGNED if options.signed else _PREVIEW_UNSIGNED
    sections = [
        instantiate(
            load_template("preview.json"),
            key="podglad_uzupelnionego_wniosku",
            params={"text": text},
        )
    ]
    if options.finish_page_style == "info_section":
        for section in sections:
            for node in section.fields:
                node.type = FieldType.INFO_SECTION
    return sections
