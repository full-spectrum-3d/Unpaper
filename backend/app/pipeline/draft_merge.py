"""Długie dokumenty: podział tekstu na fragmenty i łączenie szkiców (projekt LLM §5.4)."""

import re
from typing import Any

from app.models.draft import FormDraft

_PAGE_HEADER = re.compile(r"^=== strona \d+$")
_WHITESPACE = re.compile(r"\s+")


def split_prompt_text(text: str, max_chars: int) -> list[str]:
    """Fragmenty ≤ `max_chars`, cięte na granicach stron, potem linii, w ostateczności twardo."""
    if len(text) <= max_chars:
        return [text]
    units: list[str] = []
    for page in _split_pages(text):
        if len(page) <= max_chars:
            units.append(page)
            continue
        for line in page.split("\n"):
            units.extend(line[i : i + max_chars] for i in range(0, max(len(line), 1), max_chars))
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n{unit}" if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


def merge_drafts(drafts: list[FormDraft]) -> FormDraft:
    """Łączy szkice fragmentów: metadane z pierwszego, pola bez powtórzeń etykiet, id f1…fn."""
    first = drafts[0]
    seen_labels: dict[str, str] = {}
    new_fields: dict[str, dict[str, Any]] = {}
    pages: list[dict[str, Any]] = []
    pages_by_title: dict[str, dict[str, Any]] = {}

    for draft in drafts:
        id_map: dict[str, str] = {}
        skipped: set[str] = set()
        for _, field in draft.iter_fields():
            key = _key(field.label)
            if key in seen_labels:
                id_map[field.id] = seen_labels[key]
                skipped.add(field.id)
            else:
                new_id = f"f{len(seen_labels) + 1}"
                seen_labels[key] = new_id
                id_map[field.id] = new_id

        for page in draft.subject_pages:
            sections = []
            for section in page.sections:
                fields = []
                for field in section.fields:
                    if field.id in skipped:
                        continue
                    data = field.model_dump()
                    data["id"] = id_map[field.id]
                    conditions = []
                    for cond in data["visible_when"]:
                        target_id = id_map[cond["field_id"]]
                        if cond["field_id"] in skipped and not _valid_target(
                            new_fields.get(target_id), cond["value"]
                        ):
                            continue
                        conditions.append({**cond, "field_id": target_id})
                    data["visible_when"] = conditions
                    new_fields[data["id"]] = data
                    fields.append(data)
                if fields:
                    sections.append({**section.model_dump(), "fields": fields})
            if not sections:
                continue
            key = _key(page.title)
            if key in pages_by_title:
                pages_by_title[key]["sections"].extend(sections)
            else:
                merged_page = {"title": page.title, "sections": sections}
                pages_by_title[key] = merged_page
                pages.append(merged_page)

    return FormDraft.model_validate(
        {
            **first.model_dump(exclude={"subject_pages", "attachments", "statements"}),
            "attachments": _union(d.attachments for d in drafts),
            "statements": _union(d.statements for d in drafts),
            "subject_pages": pages,
        }
    )


def _split_pages(text: str) -> list[str]:
    pages: list[list[str]] = []
    for line in text.split("\n"):
        if _PAGE_HEADER.match(line) or not pages:
            pages.append([line])
        else:
            pages[-1].append(line)
    return ["\n".join(lines) for lines in pages]


def _key(text: str) -> str:
    return _WHITESPACE.sub(" ", text.casefold()).strip()


def _valid_target(target: dict[str, Any] | None, value: str) -> bool:
    """Warunek na zachowany duplikat ma sens tylko, gdy duplikat ma tę opcję."""
    return target is not None and value in target["options"]


def _union(groups: Any) -> list[str]:
    out: list[str] = []
    for group in groups:
        out.extend(item for item in group if item not in out)
    return out
