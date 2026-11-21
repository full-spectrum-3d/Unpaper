"""Strony przedmiotu, warunki widoczności po id pola i flow (spec §8.1, §8.3)."""

import itertools
from collections.abc import Callable

from app.models.draft import Condition as DraftCondition
from app.models.draft import FormDraft
from app.models.form import FieldType, TabType
from app.models.warning import ConversionWarning
from app.pipeline.build.fields import (
    convert_conditions,
    map_draft_field,
    slugify,
    unresolved_condition,
)
from app.pipeline.build.ir import FieldNode, PageNode, SectionNode
from app.pipeline.build.sections import BuildOptions
from app.pipeline.issues import IssueCode


def _part_title(title: str, part: int) -> str:
    if part == 1:
        return title
    return f"{title} (cd.)" if part == 2 else f"{title} (cd. {part - 1})"


def subject_pages(
    draft: FormDraft, options: BuildOptions
) -> tuple[list[PageNode], list[ConversionWarning]]:
    pages: list[PageNode] = []
    issues: list[ConversionWarning] = []
    by_id: dict[str, FieldNode] = {}
    pending: list[tuple[FieldNode, list[DraftCondition]]] = []
    limit = max(options.max_sections_per_page, 1)
    for i, draft_page in enumerate(draft.subject_pages, start=1):
        sections: list[SectionNode] = []
        for j, draft_section in enumerate(draft_page.sections, start=1):
            fields: list[FieldNode] = []
            for k, draft_field in enumerate(draft_section.fields, start=1):
                node, field_issues = map_draft_field(draft_field, key=f"p{i}.s{j}.f{k}")
                fields.append(node)
                issues.extend(field_issues)
                by_id[draft_field.id] = node
                if draft_field.visible_when:
                    pending.append((node, draft_field.visible_when))
            if not fields:
                continue
            sections.append(
                SectionNode(
                    key=f"p{i}.s{j}",
                    type=(
                        FieldType.REPEATING_SECTION
                        if draft_section.repeating
                        else FieldType.SECTION
                    ),
                    title=draft_section.title,
                    tech_name=slugify(draft_section.title),
                    fields=fields,
                )
            )
        if not sections:
            continue
        chunks = [sections[n : n + limit] for n in range(0, len(sections), limit)]
        for part, chunk in enumerate(chunks, start=1):
            key = f"p{i}" if len(chunks) == 1 else f"p{i}_{part}"
            pages.append(PageNode(key, _part_title(draft_page.title, part), TabType.MAIN, chunk))
    issues += _resolve_conditions(pending, by_id)
    return pages, issues


def _resolve_conditions(
    pending: list[tuple[FieldNode, list[DraftCondition]]], by_id: dict[str, FieldNode]
) -> list[ConversionWarning]:
    """Warunki po id pola: dopiero po zmapowaniu wszystkich pól (typ celu jest znany)."""
    issues: list[ConversionWarning] = []
    for node, conds in pending:
        node.show_when = convert_conditions(conds, by_id, node)
        if node.show_when is None:
            bad = unresolved_condition(conds, by_id, node)
            ids = bad.field_id if bad else ""
            issues.append(
                ConversionWarning(
                    code=IssueCode.W03_CONDITION_UNRESOLVED,
                    message=f"Pole {ids} z warunku nie istnieje lub nie jest polem wyboru; "
                    "pominięto warunek.",
                    path=node.key,
                )
            )
    return issues


def flow_links(tab_ids: list[str], id_factory: Callable[[], str]) -> list[dict[str, str]]:
    return [
        {"id": id_factory(), "source": source, "target": target}
        for source, target in itertools.pairwise(tab_ids)
    ]
