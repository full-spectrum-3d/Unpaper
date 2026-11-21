"""Normalizacja szkicu LLM (projekt LLM §5.4 pkt 5).

Poprawia błędy, które nie uzasadniają ponownej próby, i każdą poprawkę zgłasza
ostrzeżeniem. Oświadczenia bierze z dokumentu (`draft_rules`), a nie od modelu.
Wynik zawsze przechodzi ponownie walidację `FormDraft`.
"""

import re
from difflib import SequenceMatcher
from typing import Any

from app.models.document import FIELD_MARKER, DocumentModel
from app.models.draft import FormDraft
from app.models.warning import ConversionWarning
from app.pipeline.draft_repair import iter_field_dicts, remove_empty_containers, repair_conditions
from app.pipeline.draft_rules import (
    applicant_field_reason,
    covered_by,
    statements_from_document,
)

STATEMENT_FIELD_COVERAGE = 0.8
LABEL_MATCH_THRESHOLD = 0.6
UPPERCASE_TITLE_RATIO = 0.8
ABBREVIATIONS = frozenset({"NIP", "PESEL", "REGON", "KRS", "RODO", "CEIDG", "VAT"})

_FILL = re.compile(r"[.…_]{3,}")
# „Załącznik 2”, „Zał. nr 3”, „2)”: pozycja listy załączników bez nazwy.
_UNNAMED_ATTACHMENT = re.compile(r"(?i)^\s*(załącznik|zał\.?)?\s*(nr\.?\s*)?\d*\s*[.)]?\s*$")
_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"\w+")
_LABEL_EDGES = re.compile(r"^[\s.…_:;,]+|[\s:;,]+$")

# Etykieta zdaniowa z blankietu („W miejscowości”) → rzeczownik w mianowniku.
# Przyimek zdejmujemy tylko wtedy, gdy reszta to jedno słowo z tego słownika.
_PREPOSITIONS = frozenset({"w", "we", "przy", "na", "do", "z", "ze"})
_NOMINATIVES = {
    "miejscowości": "Miejscowość", "ulicy": "Ulica", "obrębie": "Obręb", "gminie": "Gmina",
    "powiecie": "Powiat", "województwie": "Województwo", "mieście": "Miasto", "wsi": "Wieś",
    "dzielnicy": "Dzielnica", "osiedlu": "Osiedle", "działce": "Działka", "dniu": "Data",
    "dnia": "Data", "terminie": "Termin", "kwocie": "Kwota", "roku": "Rok",
}  # fmt: skip
# Skróty na początku etykiety; standard zakazuje skrótów w etykietach.
_ABBREVIATIONS = {"nr": "Numer", "tel": "Telefon", "ul": "Ulica"}


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
    _remove_applicant_fields(data, warnings)
    _remove_duplicate_fields(data, warnings)
    _remove_unnamed_attachments(data, warnings)
    data["statements"] = statements_from_document(doc)
    _remove_statement_fields(data, warnings)
    repair_conditions(data, warnings)
    _normalize_title_case(data, warnings)
    _check_labels(data, doc_text, warnings)
    _normalize_labels(data, warnings)
    _check_authority(draft, doc_text, warnings)
    remove_empty_containers(data, warnings)

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


def _remove_applicant_fields(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Pola dublujące sekcje predefiniowane (dane wnioskodawcy, data i podpis) usuwamy."""
    for i, page in enumerate(data["subject_pages"]):
        for j, section in enumerate(page["sections"]):
            kept = []
            for k, field in enumerate(section["fields"]):
                reason = applicant_field_reason(field["label"], [section["title"], page["title"]])
                if reason is None:
                    kept.append(field)
                    continue
                warnings.append(
                    ConversionWarning(
                        code="W20_APPLICANT_FIELD_REMOVED",
                        message=f"Usunięto pole „{field['label']}”: {reason}.",
                        path=f"subject_pages[{i}].sections[{j}].fields[{k}]",
                    )
                )
            section["fields"] = kept


def _remove_duplicate_fields(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Pole o tej samej etykiecie co wcześniejsze w tej samej sekcji to powtórzenie modelu."""
    id_map: dict[str, str] = {}
    for i, page in enumerate(data["subject_pages"]):
        for j, section in enumerate(page["sections"]):
            first: dict[str, str] = {}
            kept = []
            for k, field in enumerate(section["fields"]):
                key = _normalize(field["label"])
                if key not in first:
                    first[key] = field["id"]
                    kept.append(field)
                    continue
                id_map[field["id"]] = first[key]
                warnings.append(
                    ConversionWarning(
                        code="W25_DUPLICATE_FIELD_REMOVED",
                        message=f"Usunięto powtórzone pole „{field['label']}”.",
                        path=f"subject_pages[{i}].sections[{j}].fields[{k}]",
                    )
                )
            section["fields"] = kept
    for _, field in iter_field_dicts(data):
        for cond in field["visible_when"]:
            cond["field_id"] = id_map.get(cond["field_id"], cond["field_id"])


def _remove_unnamed_attachments(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Załączniki bez nazwy („Załącznik 2”) - z listy załączników i pola typu `file`."""
    kept = []
    for i, name in enumerate(data["attachments"]):
        if _UNNAMED_ATTACHMENT.match(name):
            warnings.append(
                ConversionWarning(
                    code="W26_UNNAMED_ATTACHMENT_REMOVED",
                    message=f"Usunięto załącznik bez nazwy „{name}”.",
                    path=f"attachments[{i}]",
                )
            )
        else:
            kept.append(name)
    data["attachments"] = kept
    for i, page in enumerate(data["subject_pages"]):
        for j, section in enumerate(page["sections"]):
            fields = []
            for k, field in enumerate(section["fields"]):
                if field["kind"] == "file" and _UNNAMED_ATTACHMENT.match(field["label"]):
                    warnings.append(
                        ConversionWarning(
                            code="W26_UNNAMED_ATTACHMENT_REMOVED",
                            message=f"Usunięto pole załącznika bez nazwy „{field['label']}”.",
                            path=f"subject_pages[{i}].sections[{j}].fields[{k}]",
                        )
                    )
                else:
                    fields.append(field)
            section["fields"] = fields


def _remove_statement_fields(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    """Pole informacyjne z treścią oświadczenia dubluje zgodę w sekcji zgód - usuwamy je."""
    statements = " ".join(data["statements"])
    if not statements:
        return
    removed = {
        id(field)
        for _, field in iter_field_dicts(data)
        if field["kind"] == "info"
        and covered_by(field["label"], statements) >= STATEMENT_FIELD_COVERAGE
    }
    for path, field in iter_field_dicts(data):
        if id(field) in removed:
            warnings.append(
                ConversionWarning(
                    code="W17_STATEMENT_REMOVED",
                    message=f"Usunięto pole „{field['label'][:80]}”: to oświadczenie "
                    "z blankietu, które trafia do sekcji zgód.",
                    path=path,
                )
            )
    for page in data["subject_pages"]:
        for section in page["sections"]:
            section["fields"] = [f for f in section["fields"] if id(f) not in removed]


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


def normalize_label(label: str) -> str:
    """Etykieta w formie rzeczownikowej: bez przyimka, skrótu i znaków brzegowych."""
    text = _LABEL_EDGES.sub("", label)
    words = text.split()
    if len(words) == 2 and words[0].casefold() in _PREPOSITIONS:
        noun = _NOMINATIVES.get(words[1].casefold())
        if noun:
            return noun
    if words and (full := _ABBREVIATIONS.get(words[0].casefold().removesuffix("."))):
        words[0] = full
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def label_variants(label: str) -> list[str]:
    """Etykieta i jej możliwe zapisy w blankiecie sprzed `normalize_label`.

    „Miejscowość” mogła być „w miejscowości”, „Numer …” mogło być „Nr …”. Służy do szukania
    źródła pola w dokumencie.
    """
    variants = [label]
    words = label.split()
    if len(words) == 1:
        variants += [form for form, noun in _NOMINATIVES.items() if noun == label]
    if len(words) > 1:
        variants += [
            " ".join([short, *words[1:]])
            for short, full in _ABBREVIATIONS.items()
            if full == words[0]
        ]
    return variants


def _normalize_labels(data: dict[str, Any], warnings: list[ConversionWarning]) -> None:
    for path, field in iter_field_dicts(data):
        fixed = normalize_label(field["label"])
        if fixed and fixed != field["label"]:
            warnings.append(
                ConversionWarning(
                    code="W32_LABEL_NORMALIZED",
                    message=f"Etykietę „{field['label']}” poprawiono na „{fixed}”.",
                    path=path,
                )
            )
            field["label"] = fixed


def _check_labels(data: dict[str, Any], doc_text: str, warnings: list[ConversionWarning]) -> None:
    for path, field in iter_field_dicts(data):
        if not matches_text(field["label"], doc_text, LABEL_MATCH_THRESHOLD):
            warnings.append(
                ConversionWarning(
                    code="W13_FIELD_NOT_IN_DOCUMENT",
                    message=f"Pola „{field['label']}” nie znaleziono w treści blankietu - "
                    "sprawdź je.",
                    path=path,
                )
            )


def _check_authority(draft: FormDraft, doc_text: str, warnings: list[ConversionWarning]) -> None:
    """Każde słowo adresata (min. 3 litery) musi mieć w dokumencie słowo o wspólnym rdzeniu."""
    doc_words = _WORD.findall(_normalize(doc_text))
    missing = [
        word
        for word in _WORD.findall(_normalize(draft.authority_name))
        if len(word) >= 3 and not any(_same_stem(word, d) for d in doc_words)
    ]
    if missing:
        warnings.append(
            ConversionWarning(
                code="W19_AUTHORITY_NOT_IN_DOCUMENT",
                message=f"Adresata „{draft.authority_name}” nie znaleziono w treści blankietu "
                f"(brak: {', '.join(missing)}) - sprawdź nazwę urzędu lub organu.",
                path="authority_name",
            )
        )


def _same_stem(word: str, other: str) -> bool:
    """Wspólny początek o długości słowa minus 2 (min. 3) - toleruje polską odmianę."""
    need = min(len(word), max(3, len(word) - 2))
    return len(other) >= need and word[:need] == other[:need]
