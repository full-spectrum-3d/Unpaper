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
    """Łączy szkice fragmentów: metadane z pierwszego, id f1…fn.

    Fragmenty z `split_prompt_text` się nie nakładają, więc pola o tej samej etykiecie
    w różnych fragmentach (np. dane drugiej osoby) zostają. Warunki wskazują pola
    z tego samego fragmentu, więc po przenumerowaniu zawsze trafiają w istniejące pole.
    """
    first = drafts[0]
    pages: list[dict[str, Any]] = []
    pages_by_title: dict[str, dict[str, Any]] = {}

    counter = 0
    for draft in drafts:
        id_map: dict[str, str] = {}
        for _, field in draft.iter_fields():
            counter += 1
            id_map[field.id] = f"f{counter}"

        for page in draft.subject_pages:
            sections = []
            for section in page.sections:
                fields = []
                for field in section.fields:
                    data = field.model_dump()
                    data["id"] = id_map[field.id]
                    data["visible_when"] = [
                        {**cond, "field_id": id_map[cond["field_id"]]}
                        for cond in data["visible_when"]
                    ]
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


def _union(groups: Any) -> list[str]:
    out: list[str] = []
    for group in groups:
        out.extend(item for item in group if item not in out)
    return out
