"""Normalizacja szkicu LLM (projekt LLM §5.4 pkt 5).

Poprawia błędy, które nie uzasadniają ponownej próby, i każdą poprawkę zgłasza
ostrzeżeniem. Wynik zawsze przechodzi ponownie walidację `FormDraft`.
"""

import re
from difflib import SequenceMatcher
from typing import Any

from app.models.document import FIELD_MARKER, DocumentModel
from app.models.draft import FormDraft
from app.models.warning import ConversionWarning

STATEMENT_MATCH_THRESHOLD = 0.8
LABEL_MATCH_THRESHOLD = 0.6
UPPERCASE_TITLE_RATIO = 0.8
ABBREVIATIONS = frozenset({"NIP", "PESEL", "REGON", "KRS", "RODO", "CEIDG", "VAT"})

_FILL = re.compile(r"[.…_]{3,}")
_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"\w+")


def matches_text(needle: str, haystack: str, threshold: float) -> bool:
    """Czy `needle` występuje w `haystack` (najdłuższy wspólny fragment ≥ próg długości)."""
    n, h = _normalize(needle), _normalize(haystack)
    if not n:
        return True
    match = SequenceMatcher(None, n, h, autojunk=False).find_longest_match(0, len(n), 0, len(h))
    return match.size / len(n) >= threshold


def normalize_draft(
    draft: FormDraft, doc: DocumentModel
) -> tuple[FormDraft, list[ConversionWarning]]:
    warnings: list[ConversionWarning] = []
    doc_text = doc.to_prompt_text(exclude_boilerplate=True)
    data = draft.model_dump()

    _downgrade_choices_without_options(draft, data, warnings)
    _filter_statements(data, doc_text, warnings)
    _normalize_title_case(data, warnings)
    _check_labels(draft, doc_text, warnings)
    _remove_empty_pages(data, warnings)

    return FormDraft.model_validate(data), warnings


def _normalize(text: str) -> str:
    text = text.casefold().replace(FIELD_MARKER.casefold(), " ")
    text = _FILL.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def _fields_by_path(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i, page in enumerate(data["subject_pages"]):
        for j, section in enumerate(page["sections"]):
            for k, field in enumerate(section["fields"]):
                out[f"subject_pages[{i}].sections[{j}].fields[{k}]"] = field
    return out


def _downgrade_choices_without_options(
    draft: FormDraft, data: dict[str, Any], warnings: list[ConversionWarning]
) -> None:
    fields = _fields_by_path(data)
    downgraded: set[str] = set()
    for path, field in draft.iter_fields():
        too_few = (field.kind == "single_choice" and len(field.options) < 2) or (
            field.kind == "multi_choice" and not field.options
        )
        if too_few:
            fields[path].update(kind="short_text", options=[])
            downgraded.add(field.id)
            warnings.append(
                ConversionWarning(
                    code="W15_CHOICE_WITHOUT_OPTIONS",
                    message=f"Pole „{field.label}” nie miało opcji wyboru - zamienione na tekst.",
                    path=path,
                )
            )
    if not downgraded:
        return
    for path, raw in fields.items():
        kept = [c for c in raw["visible_when"] if c["field_id"] not in downgraded]
        if len(kept) != len(raw["visible_when"]):
            raw["visible_when"] = kept
            warnings.append(
                ConversionWarning(
                    code="W15_CHOICE_WITHOUT_OPTIONS",
                    message=f"Usunięto warunek widoczności pola „{raw['label']}”: "
                    "pole, od którego zależał, nie jest już polem wyboru.",
                    path=path,
                )
            )


def _filter_statements(
    data: dict[str, Any], doc_text: str, warnings: list[ConversionWarning]
) -> None:
    kept = []
    for i, statement in enumerate(data["statements"]):
        if _FILL.search(statement) or not matches_text(
            statement, doc_text, STATEMENT_MATCH_THRESHOLD
        ):
            warnings.append(
                ConversionWarning(
                    code="W17_STATEMENT_REMOVED",
                    message=f"Usunięto oświadczenie spoza treści blankietu: „{statement[:80]}”.",
                    path=f"statements[{i}]",
                )
            )
        else:
            kept.append(statement)
    data["statements"] = kept


def _normalize_title_case(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    title: str = data["title"]
    letters = [c for c in title if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < UPPERCASE_TITLE_RATIO:
        return
    fixed = title[0].upper() + title[1:].lower()
    fixed = _WORD.sub(
        lambda m: m.group().upper() if m.group().upper() in ABBREVIATIONS else m.group(), fixed
    )
    data["title"] = fixed
    warnings.append(
        ConversionWarning(
            code="W16_TITLE_CASE_NORMALIZED",
            message=f"Tytuł zapisany wielkimi literami poprawiono na „{fixed}”.",
            path="title",
        )
    )


def _check_labels(draft: FormDraft, doc_text: str, warnings: list[ConversionWarning]) -> None:
    for path, field in draft.iter_fields():
        if not matches_text(field.label, doc_text, LABEL_MATCH_THRESHOLD):
            warnings.append(
                ConversionWarning(
                    code="W13_FIELD_NOT_IN_DOCUMENT",
                    message=f"Pola „{field.label}” nie znaleziono w treści blankietu - sprawdź je.",
                    path=path,
                )
            )


def _remove_empty_pages(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    kept = []
    for i, page in enumerate(data["subject_pages"]):
        if page["sections"]:
            kept.append(page)
        else:
            warnings.append(
                ConversionWarning(
                    code="W18_EMPTY_CONTAINER_REMOVED",
                    message=f"Usunięto pustą stronę „{page['title']}”.",
                    path=f"subject_pages[{i}]",
                )
            )
    data["subject_pages"] = kept
