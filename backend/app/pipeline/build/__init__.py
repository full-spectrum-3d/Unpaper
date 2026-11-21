"""[5] Deterministyczna budowa FormDefinition z FormDraft (spec §5.5, §8)."""

from dataclasses import dataclass, field

from app.models.dictionary import DictionaryProposal
from app.models.draft import DraftField, DraftPage, DraftSection, FormDraft
from app.models.form import FieldType, FormDefinition, TabType
from app.models.warning import ConversionWarning
from app.pipeline.build.dictionaries import apply_dictionaries
from app.pipeline.build.fields import assign_unique_tech_names, normalize_title
from app.pipeline.build.html import accessible_links
from app.pipeline.build.initial_data import apply_initial_data
from app.pipeline.build.ir import PageNode
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
from app.pipeline.issues import IssueCode

_DEFAULT_OPTIONS = BuildOptions()

__all__ = ["BuildOptions", "BuildResult", "build_fallback", "build_form"]


@dataclass
class BuildResult:
    form: FormDefinition
    warnings: list[ConversionWarning]
    # Do raportu: `report.dictionaryProposals` (spec §6.2, §8.6).
    dictionary_proposals: list[DictionaryProposal] = field(default_factory=list)


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


def _make_links_accessible(pages: list[PageNode]) -> None:
    for page in pages:
        for section in page.sections:
            section.description_html = accessible_links(section.description_html)
            for node in section.fields:
                node.description_html = accessible_links(node.description_html)
                for consent in node.consents:
                    consent.description_html = accessible_links(consent.description_html)


def build_form(draft: FormDraft, options: BuildOptions = _DEFAULT_OPTIONS) -> BuildResult:
    draft = _normalized(draft)
    warnings: list[ConversionWarning] = []
    title, issues = normalize_title(draft.title)
    warnings += issues

    pages = [PageNode("dane", "Dane", TabType.MAIN, applicant_page_sections(draft, options))]
    subject, issues = subject_pages(draft, options)
    pages += subject
    warnings += issues

    existing = {
        _label_key(node.title)
        for page in subject
        for section in page.sections
        for node in section.fields
        if node.type is FieldType.FILE_UPLOADER
    }
    extra: list[str] = []
    for label in draft.attachments:
        if _label_key(label) in existing:
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
    warnings += apply_initial_data(pages)
    states, issues = build_states(pages)
    warnings += issues
    form = FormDefinition.model_validate(
        to_form_definition(title, pages, states, options.id_factory)
    )
    return BuildResult(form, warnings, propose_dictionaries(form))


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
