"""[5] Deterministyczna budowa FormDefinition z FormDraft (spec §5.5, §8)."""

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.dictionary import DictionaryProposal
from app.models.draft import CHOICE_KINDS, DraftField, DraftPage, DraftSection, FormDraft
from app.models.form import FieldType, FormDefinition, TabType
from app.models.warning import ConversionWarning
from app.pipeline.build.dictionaries import apply_dictionaries
from app.pipeline.build.fields import assign_unique_tech_names, normalize_title
from app.pipeline.build.html import accessible_links
from app.pipeline.build.initial_data import apply_initial_data
from app.pipeline.build.ir import PageNode, iter_fields
from app.pipeline.build.pages import subject_pages
from app.pipeline.build.proposals import propose_dictionaries
from app.pipeline.build.sections import (
    BuildOptions,
    applicant_page_sections,
    contact_page_sections,
    finish_page_sections,
)
from app.pipeline.build.serialize import to_form_definition
from app.pipeline.build.states import build_states
from app.pipeline.draft_normalize import LABEL_MATCH_THRESHOLD, matches_text
from app.pipeline.draft_repair import iter_field_dicts, remove_empty_containers, repair_conditions
from app.pipeline.issues import IssueCode

_DEFAULT_OPTIONS = BuildOptions()

__all__ = ["BuildOptions", "BuildResult", "build_fallback", "build_form"]


@dataclass
class BuildResult:
    form: FormDefinition
    warnings: list[ConversionWarning]
    # Do raportu: `report.dictionaryProposals` (spec §6.2, §8.6).
    dictionary_proposals: list[DictionaryProposal] = field(default_factory=list)
    # techName pola → klucz węzła (`p1.s2.f3` dla pól ze szkicu); do mapy pochodzenia w raporcie.
    field_keys: dict[str, str] = field(default_factory=dict)


def _label_key(label: str) -> str:
    return " ".join(label.split()).casefold()


def _normalized(draft: FormDraft) -> FormDraft:
    attachments: dict[str, str] = {}
    for label in draft.attachments:
        attachments.setdefault(_label_key(label), label)
    kinds = list(draft.applicant_kinds)
    if kinds == ["OTHER_PERSON"]:
        kinds.insert(0, "SELF")
    return draft.model_copy(
        update={"applicant_kinds": kinds, "attachments": list(attachments.values())}
    )


_POWER_OF_ATTORNEY = re.compile(r"(?i)pełnomocnictw")
_YES_NO = frozenset({"tak", "nie"})
# Rodzaje wnioskodawcy, dla których powstaje sekcja predefiniowana „Pełnomocnictwo”
# (z opłatą skarbową): `applicant_page_sections`.
_REPRESENTED_KINDS = frozenset({"OTHER_PERSON", "LEGAL_ENTITY"})


def _is_power_of_attorney_field(field: dict[str, Any]) -> bool:
    """Plik albo pytanie Tak/Nie o pełnomocnictwo; „Numer pełnomocnictwa” zostaje."""
    if not _POWER_OF_ATTORNEY.search(field["label"]):
        return False
    if field["kind"] == "file":
        return True
    options = {option.strip().casefold() for option in field["options"]}
    return field["kind"] in CHOICE_KINDS and bool(options) and options <= _YES_NO


def _without_power_of_attorney(draft: FormDraft) -> tuple[FormDraft, list[ConversionWarning]]:
    """Pełnomocnictwo i opłatę skarbową za nie zbiera sekcja predefiniowana (warunkowo);
    te same pliki ze szkicu (załączniki, pola przedmiotu) byłyby wymagane zawsze."""
    if not _REPRESENTED_KINDS.intersection(draft.applicant_kinds):
        return draft, []
    warnings: list[ConversionWarning] = []

    def removed(label: str, path: str) -> None:
        warnings.append(
            ConversionWarning(
                code=IssueCode.W41_POWER_OF_ATTORNEY_DUPLICATE_REMOVED,
                message=f"Usunięto „{label}”: pełnomocnictwo i opłatę skarbową za nie "
                "zbiera sekcja predefiniowana.",
                path=path,
            )
        )

    data = draft.model_dump()
    attachments = []
    for i, label in enumerate(data["attachments"]):
        if _POWER_OF_ATTORNEY.search(label):
            removed(label, f"attachments[{i}]")
        else:
            attachments.append(label)
    dropped: set[int] = set()
    for path, item in iter_field_dicts(data):
        if _is_power_of_attorney_field(item):
            dropped.add(id(item))
            removed(item["label"], path)
    if not warnings:
        return draft, []
    data["attachments"] = attachments
    for page in data["subject_pages"]:
        for section in page["sections"]:
            section["fields"] = [f for f in section["fields"] if id(f) not in dropped]
    repair_conditions(data, warnings)
    remove_empty_containers(data, warnings)
    return FormDraft.model_validate(data), warnings


def _is_duplicate_label(label: str, other: str) -> bool:
    return matches_text(label, other, LABEL_MATCH_THRESHOLD) or matches_text(
        other, label, LABEL_MATCH_THRESHOLD
    )


def _make_links_accessible(pages: list[PageNode]) -> None:
    for page in pages:
        for section in page.sections:
            section.description_html = accessible_links(section.description_html)
            for node in section.fields:
                node.description_html = accessible_links(node.description_html)
                for consent in node.consents:
                    consent.description_html = accessible_links(consent.description_html)


def build_form(draft: FormDraft, options: BuildOptions = _DEFAULT_OPTIONS) -> BuildResult:
    draft, warnings = _without_power_of_attorney(_normalized(draft))
    title, issues = normalize_title(draft.title)
    warnings += issues

    pages = [PageNode("dane", "Dane", TabType.MAIN, applicant_page_sections(draft, options))]
    subject, issues = subject_pages(draft, options)
    pages += subject
    warnings += issues

    existing = [
        node.title
        for page in subject
        for section in page.sections
        for node in section.fields
        if node.type is FieldType.FILE_UPLOADER
    ]
    extra: list[str] = []
    for label in draft.attachments:
        if any(_is_duplicate_label(label, other) for other in existing):
            warnings.append(
                ConversionWarning(
                    code=IssueCode.W10_ATTACHMENT_DUPLICATE,
                    message=f"Pominięto załącznik „{label}”: jest już polem formularza.",
                )
            )
        else:
            extra.append(label)
    pages.append(
        PageNode(
            "kontakt", "Kontakt i zgody", TabType.MAIN, contact_page_sections(draft, options, extra)
        )
    )
    pages.append(
        PageNode("koniec", "Strona końcowa", TabType.FINISH, finish_page_sections(draft, options))
    )

    if not options.rodo_clause_url:
        warnings.append(
            ConversionWarning(
                code=IssueCode.W28_RODO_CLAUSE_URL_MISSING,
                message="Zgoda RODO nie ma linku do klauzuli informacyjnej: ustaw "
                "RODO_CLAUSE_URL (np. adres w BIP) albo dodaj link w Generatorze.",
            )
        )
    _make_links_accessible(pages)
    assign_unique_tech_names(pages)
    apply_dictionaries(pages)
    warnings += apply_initial_data(pages, infer_subject=set(draft.applicant_kinds) == {"SELF"})
    states, issues = build_states(pages)
    warnings += issues
    form = FormDefinition.model_validate(
        to_form_definition(title, pages, states, options.id_factory)
    )
    field_keys = {node.tech_name: node.key for _, _, node in iter_fields(pages)}
    return BuildResult(form, warnings, propose_dictionaries(form), field_keys)


def build_fallback(
    title: str | None = None,
    authority_name: str = "",
    options: BuildOptions = _DEFAULT_OPTIONS,
) -> BuildResult:
    # model_construct: FormDraft nie przyjmuje pustego authority_name, a fallback go nie zna.
    draft = FormDraft.model_construct(
        title=title or "Wniosek",
        authority_kind="URZAD",
        authority_name=authority_name,
        applicant_kinds=["SELF", "OTHER_PERSON"],
        attachments=[],
        statements=[],
        subject_pages=[
            DraftPage(
                title="Treść wniosku",
                sections=[
                    DraftSection(
                        title="Treść wniosku",
                        repeating=False,
                        fields=[
                            DraftField(
                                id="f1",
                                label="Treść wniosku",
                                kind="long_text",
                                required=True,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    result = build_form(draft, options)
    result.warnings.insert(
        0,
        ConversionWarning(
            code=IssueCode.W01_LLM_FALLBACK, message="Użyto formularza zastępczego (błąd LLM)."
        ),
    )
    return result
