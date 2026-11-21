"""Naprawa odpowiedzi LLM: `LlmDraft` → spójny `FormDraft` (projekt LLM §5.4 pkt 5).

Błędy odwołań między polami (warunek na polu tekstowym, nieistniejące id, powtórzone
id) poprawiamy w kodzie zamiast ponawiać wywołanie modelu - na CPU ponowienie trwa
minuty. Każda poprawka to ostrzeżenie; ponowienie zostaje tylko dla odpowiedzi
niezgodnych ze schematem (np. ucięty JSON).
"""

import re
from typing import Any

from app.models.draft import CHOICE_KINDS, FormDraft, LlmDraft
from app.models.warning import ConversionWarning

DEFAULT_APPLICANT_KINDS = ["SELF", "OTHER_PERSON"]

_ID = re.compile(r"^f(\d+)$")


def repair_draft(raw: LlmDraft) -> tuple[FormDraft, list[ConversionWarning]]:
    warnings: list[ConversionWarning] = []
    data = raw.model_dump()
    data["statements"] = []
    data["applicant_kinds"] = list(dict.fromkeys(data["applicant_kinds"])) or list(
        DEFAULT_APPLICANT_KINDS
    )
    _renumber_ids(data, warnings)
    repair_conditions(data, warnings)
    remove_empty_containers(data, warnings)
    return FormDraft.model_validate(data), warnings


def iter_field_dicts(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Pola szkicu (słowniki) ze ścieżką `subject_pages[i].sections[j].fields[k]`."""
    return [
        (f"subject_pages[{i}].sections[{j}].fields[{k}]", field)
        for i, page in enumerate(data["subject_pages"])
        for j, section in enumerate(page["sections"])
        for k, field in enumerate(section["fields"])
    ]


def repair_conditions(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Usuwa warunki, które nie wskazują istniejącej opcji innego pola wyboru."""
    fields = iter_field_dicts(data)
    by_id: dict[str, dict[str, Any]] = {}
    for _, field in fields:
        by_id.setdefault(field["id"], field)
    for path, field in fields:
        kept: list[dict[str, Any]] = []
        for cond in field["visible_when"]:
            reason = _fix_condition(cond, field, by_id.get(cond["field_id"]))
            if reason is None:
                if cond not in kept:
                    kept.append(cond)
                continue
            warnings.append(
                ConversionWarning(
                    code="W21_CONDITION_REMOVED",
                    message=f"Usunięto warunek widoczności pola „{field['label']}”: {reason}.",
                    path=path,
                )
            )
        field["visible_when"] = kept


def remove_empty_containers(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Usuwa sekcje bez pól, a potem strony bez sekcji."""
    pages = []
    for i, page in enumerate(data["subject_pages"]):
        sections = []
        for j, section in enumerate(page["sections"]):
            if section["fields"]:
                sections.append(section)
                continue
            warnings.append(
                ConversionWarning(
                    code="W18_EMPTY_CONTAINER_REMOVED",
                    message=f"Usunięto pustą sekcję „{section['title']}”.",
                    path=f"subject_pages[{i}].sections[{j}]",
                )
            )
        page["sections"] = sections
        if sections:
            pages.append(page)
            continue
        warnings.append(
            ConversionWarning(
                code="W18_EMPTY_CONTAINER_REMOVED",
                message=f"Usunięto pustą stronę „{page['title']}”.",
                path=f"subject_pages[{i}]",
            )
        )
    data["subject_pages"] = pages


def _renumber_ids(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Puste i powtórzone id dostają kolejne wolne `fN`; warunki wskazują pierwsze wystąpienie."""
    fields = iter_field_dicts(data)
    used = {f["id"].strip() for _, f in fields}
    numbers = [int(m.group(1)) for fid in used if (m := _ID.match(fid))]
    next_number = max(numbers, default=0) + 1
    seen: set[str] = set()
    for path, field in fields:
        fid = field["id"].strip()
        if fid and fid not in seen:
            field["id"] = fid
            seen.add(fid)
            continue
        while f"f{next_number}" in used:
            next_number += 1
        field["id"] = f"f{next_number}"
        used.add(field["id"])
        seen.add(field["id"])
        warnings.append(
            ConversionWarning(
                code="W22_FIELD_ID_RENUMBERED",
                message=f"Pole „{field['label']}” miało powtórzone lub puste id "
                f"(„{fid}”) - nadano {field['id']}.",
                path=path,
            )
        )


def _fix_condition(
    cond: dict[str, Any], field: dict[str, Any], target: dict[str, Any] | None
) -> str | None:
    """Przyczyna odrzucenia warunku albo None; wartość różniąca się wielkością liter poprawia."""
    if target is None:
        return f"pole {cond['field_id']} nie istnieje"
    if target is field:
        return "pole nie może zależeć od siebie"
    if target["kind"] not in CHOICE_KINDS:
        return f"pole „{target['label']}” nie jest polem wyboru"
    if cond["value"] in target["options"]:
        return None
    wanted = cond["value"].strip().casefold()
    for option in target["options"]:
        if option.strip().casefold() == wanted:
            cond["value"] = option
            return None
    return f"„{cond['value']}” nie jest opcją pola „{target['label']}”"
