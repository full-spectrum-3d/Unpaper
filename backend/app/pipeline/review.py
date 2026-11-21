"""Mapa pochodzenia pól i lista „do sprawdzenia” (raport konwersji).

Dla każdego pola formularza ustalamy, skąd się wzięło: z szablonu sekcji predefiniowanej
albo z konkretnego bloku dokumentu (strona, tekst, położenie). Pola z dokumentu dostają
ocenę pewności z prostych, jawnych sygnałów - to heurystyka wskazująca urzędnikowi, co
przejrzeć w pierwszej kolejności, a nie prawdopodobieństwo poprawności.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from app.models.document import Block, DocumentModel, Page
from app.models.draft import DraftField, FormDraft
from app.models.form import SECTION_TYPES, FieldType
from app.models.warning import ConversionWarning
from app.pipeline.draft_normalize import LABEL_MATCH_THRESHOLD, label_variants, matches_text

HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.55
LOW_OCR_CONFIDENCE = 0.7
OPTION_MATCH_THRESHOLD = 0.8
# Dopasowania gorsze od najlepszego o mniej niż tyle uznajemy za równorzędne.
MATCH_TIE = 0.05
SOURCE_TEXT_LIMIT = 200
MIN_FUZZY_LENGTH = 6
# Szkic z reguł: typy pól i etykiety zgadywane bez modelu, więc cały wynik jest mniej pewny.
RULE_BASED_FACTOR = 0.85

_SUBJECT_KEY = re.compile(r"^p(\d+)(?:_\d+)?\.s(\d+)\.f(\d+)$")
_ATTACHMENT_KEY = re.compile(r"^zalaczniki\.zalacznik_(\d+)")
_FILL = re.compile(r"[.…_]{3,}")
_WHITESPACE = re.compile(r"\s+")
_NOT_REVIEWED = frozenset({FieldType.TEXT_BLOCK, FieldType.INFO_SECTION})

# Ostrzeżenia o całym formularzu: poziom na liście „do sprawdzenia”. Pozostałe kody bez
# wskazanego pola są informacyjne i na listę nie trafiają (zostają w `report.warnings`).
_FORM_LEVELS: dict[str, str] = {
    "W27_FORM_REBUILT": "low",
    "W01_LLM_FALLBACK": "low",
    "W11_OCR_UNAVAILABLE": "low",
    "W14_PARTIAL_ANALYSIS": "low",
    "W12_LOW_OCR_CONFIDENCE": "medium",
    "W24_RULE_BASED_DRAFT": "medium",
    "W19_AUTHORITY_NOT_IN_DOCUMENT": "medium",
    "W05_TITLE_PREFIX": "medium",
    "W31_TITLE_LEGAL_REFERENCE": "medium",
}
# Sygnały o całym formularzu obniżające wynik łączny.
_FORM_PENALTIES: dict[str, float] = {
    "W01_LLM_FALLBACK": 0.8,
    "W14_PARTIAL_ANALYSIS": 0.8,
    "W11_OCR_UNAVAILABLE": 0.7,
}


@dataclass(frozen=True, slots=True)
class _Located:
    page: Page
    block: Block
    index: int
    ratio: float


@dataclass(slots=True)
class _Score:
    value: float = 1.0
    reasons: list[dict[str, str]] = field(default_factory=list)

    def lower(self, factor: float, code: str, message: str) -> None:
        self.value *= factor
        self.reasons.append({"code": code, "message": message})


def _norm(text: str) -> str:
    return _WHITESPACE.sub(" ", _FILL.sub(" ", text.casefold())).strip()


def _level(score: float) -> str:
    if score >= HIGH_CONFIDENCE:
        return "high"
    return "medium" if score >= MEDIUM_CONFIDENCE else "low"


class _Locator:
    """Szuka bloku dokumentu z etykietą pola; przy remisie trzyma się kolejności dokumentu."""

    def __init__(self, document: DocumentModel) -> None:
        pages = {page.number: page for page in document.pages}
        self._blocks = [
            (pages[number], block, _norm(block.text))
            for number, block in document.iter_content_blocks()
        ]
        self._cursor = -1

    def find(self, label: str) -> _Located | None:
        needles = [n for n in map(_norm, label_variants(label)) if n]
        hits: list[tuple[float, int]] = []
        for index, (_, _, text) in enumerate(self._blocks):
            if not text:
                continue
            ratio = max((self._ratio(needle, text) for needle in needles), default=0.0)
            if ratio >= LABEL_MATCH_THRESHOLD:
                hits.append((ratio, index))
        if not hits:
            return None
        top = max(ratio for ratio, _ in hits)
        best = [item for item in hits if item[0] >= top - MATCH_TIE]
        # Etykiety typu „Data” powtarzają się: bierzemy pierwsze trafienie za poprzednim polem,
        # a gdy takiego nie ma - najkrótszy blok (najbliższy samej etykiecie).
        after = [item for item in best if item[1] >= self._cursor]
        ratio, index = (
            after[0] if after else min(best, key=lambda item: len(self._blocks[item[1]][2]))
        )
        self._cursor = max(self._cursor, index)
        page, block, _ = self._blocks[index]
        return _Located(page, block, index, min(ratio, 1.0))

    @staticmethod
    def _ratio(needle: str, text: str) -> float:
        # Za słowem może stać cyfra odsyłacza („ulicy1)”), ale nie litera.
        if re.search(rf"(?<!\w){re.escape(needle)}(?![^\W\d])", text):
            return 1.0
        if len(needle) < MIN_FUZZY_LENGTH:
            # Krótka etykieta („Data”, „Rok”) pasowałaby do środka przypadkowych słów.
            return 0.0
        matcher = SequenceMatcher(None, needle, text, autojunk=False)
        size = matcher.find_longest_match(0, len(needle), 0, len(text)).size
        return size / len(needle)


def _source(found: _Located) -> dict[str, Any]:
    text = _WHITESPACE.sub(" ", _FILL.sub(" … ", found.block.text)).strip()
    if len(text) > SOURCE_TEXT_LIMIT:
        text = text[: SOURCE_TEXT_LIMIT - 1].rstrip() + "…"
    source: dict[str, Any] = {"page": found.page.number, "blockId": found.block.id, "text": text}
    box, page = found.block.bbox, found.page
    if box is not None and page.width and page.height:
        # Ułamki strony (0-1): niezależne od rozdzielczości podglądu.
        source["box"] = {
            "x": round(min(max(box.x0 / page.width, 0.0), 1.0), 4),
            "y": round(min(max(box.y0 / page.height, 0.0), 1.0), 4),
            "width": round(min(max((box.x1 - box.x0) / page.width, 0.0), 1.0), 4),
            "height": round(min(max((box.y1 - box.y0) / page.height, 0.0), 1.0), 4),
        }
        source["pageAspect"] = round(page.width / page.height, 4)
    if found.block.ocr_confidence is not None:
        source["ocrConfidence"] = round(found.block.ocr_confidence, 3)
    return source


def _draft_field(draft: FormDraft, key: str) -> DraftField | None:
    match = _SUBJECT_KEY.match(key)
    if match is None:
        return None
    page, section, index = (int(group) - 1 for group in match.groups())
    try:
        return draft.subject_pages[page].sections[section].fields[index]
    except IndexError:
        return None


def _score_document_field(
    label: str,
    options: list[str],
    found: _Located | None,
    doc_text: str,
    *,
    field_warnings: list[ConversionWarning],
) -> _Score:
    score = _Score()
    if found is None:
        score.lower(
            0.35,
            "LABEL_NOT_IN_DOCUMENT",
            f"Etykiety „{label}” nie ma w treści dokumentu - pole mogło zostać dopisane.",
        )
    else:
        score.value *= 0.7 + 0.3 * found.ratio
        confidence = found.block.ocr_confidence
        if confidence is not None:
            if confidence < LOW_OCR_CONFIDENCE:
                score.lower(
                    0.5 + 0.5 * confidence,
                    "LOW_OCR_CONFIDENCE",
                    f"Fragment skanu odczytano z pewnością {confidence:.0%} - sprawdź pisownię.",
                )
            else:
                score.value *= 0.5 + 0.5 * confidence
    missing = [o for o in options if not matches_text(o, doc_text, OPTION_MATCH_THRESHOLD)]
    if missing:
        listed = ", ".join(f"„{option}”" for option in missing[:3])
        more = f" i {len(missing) - 3} innych" if len(missing) > 3 else ""
        score.lower(
            0.5 + 0.5 * (len(options) - len(missing)) / len(options),
            "OPTIONS_NOT_IN_DOCUMENT",
            f"Opcji {listed}{more} nie ma w treści dokumentu.",
        )
    for warning in field_warnings:
        score.lower(0.8, warning.code, warning.message)
    return score


def _iter_form_fields(form: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Pola formularza jako (tytuł strony, tytuł sekcji, pole); bez bloków tekstu."""
    result: list[tuple[str, str, dict[str, Any]]] = []
    for tab in form.get("tabs", []):
        for question in tab.get("questions", []):
            top = question.get("field", {})
            if top.get("type") not in SECTION_TYPES:
                children = [top]
                section = ""
            else:
                children = [c.get("field", {}) for c in top.get("repeatingSectionGrid") or []]
                section = str(top.get("title", ""))
            for child in children:
                if child.get("type") not in _NOT_REVIEWED:
                    result.append((str(tab.get("title", "")), section, child))
    return result


def _field_label(node: dict[str, Any]) -> str:
    """Tytuł pola; pola bez tytułu (zgody, checkbox „Brak …”) opisuje pierwsza opcja."""
    if title := str(node.get("title") or "").strip():
        return title
    options = node.get("options") or []
    if options and isinstance(options[0], dict):
        return str(options[0].get("name", ""))
    return "Zgody i oświadczenia" if node.get("type") == FieldType.CONSENT_SECTION else ""


def build_review(
    document: DocumentModel,
    draft: FormDraft | None,
    form: dict[str, Any],
    field_keys: dict[str, str],
    warnings: list[ConversionWarning],
) -> dict[str, Any]:
    """Klucze raportu `confidence`, `fields` i `review`.

    `draft=None` oznacza formularz zastępczy: żadne pole nie pochodzi wtedy z dokumentu.
    """
    codes = {warning.code for warning in warnings}
    rule_based = "W24_RULE_BASED_DRAFT" in codes
    doc_text = document.to_prompt_text(exclude_boilerplate=True)
    locator = _Locator(document)
    key_of = dict(field_keys)
    by_path: dict[str, list[ConversionWarning]] = {}
    for warning in warnings:
        if warning.path:
            by_path.setdefault(warning.path, []).append(warning)

    fields: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    scores: list[float] = []
    for tab, section, node in _iter_form_fields(form):
        tech_name = str(node.get("techName", ""))
        key = key_of.get(tech_name, "")
        entry: dict[str, Any] = {
            "techName": tech_name,
            "title": _field_label(node),
            "tab": tab,
            "section": section,
        }
        draft_field = _draft_field(draft, key) if draft is not None else None
        attachment = draft is not None and _ATTACHMENT_KEY.match(key) is not None
        if draft_field is None and not attachment:
            # Sekcje predefiniowane: treść ze standardu, niezależna od dokumentu.
            entry |= {"origin": "template", "confidence": 1.0, "level": "high", "reasons": []}
            fields.append(entry)
            continue
        label = draft_field.label if draft_field else entry["title"]
        found = locator.find(label)
        related = [*by_path.get(key, []), *by_path.get(tech_name, [])]
        score = _score_document_field(
            label,
            list(draft_field.options) if draft_field else [],
            found,
            doc_text,
            field_warnings=related,
        )
        value = round(min(max(score.value, 0.0), 1.0), 2)
        entry |= {
            "origin": "document",
            "confidence": value,
            "level": _level(value),
            "reasons": score.reasons,
        }
        if found is not None:
            entry["source"] = _source(found)
        fields.append(entry)
        scores.append(value)
        if entry["level"] != "high":
            review.append(
                {
                    "kind": "field",
                    "level": entry["level"],
                    "techName": tech_name,
                    "title": entry["title"],
                    "tab": tab,
                    "messages": [reason["message"] for reason in score.reasons]
                    or ["Etykieta tylko częściowo zgadza się z treścią dokumentu."],
                }
            )

    for warning in warnings:
        level = _FORM_LEVELS.get(warning.code)
        if level is not None:
            review.append(
                {
                    "kind": "form",
                    "level": level,
                    "code": warning.code,
                    "title": "Cały formularz",
                    "messages": [warning.message],
                }
            )
    review.sort(key=lambda item: 0 if item["level"] == "low" else 1)

    if scores:
        overall = sum(scores) / len(scores)
        for code, factor in _FORM_PENALTIES.items():
            if code in codes:
                overall *= factor
        if rule_based and "W01_LLM_FALLBACK" not in codes:
            overall *= RULE_BASED_FACTOR
    else:
        # Brak pól z dokumentu: formularz zastępczy albo sam szablon - wszystko do uzupełnienia.
        overall = 0.0
    overall = round(overall, 2)
    return {
        "confidence": {
            "score": overall,
            "level": _level(overall),
            "fieldsTotal": len(fields),
            "fieldsFromDocument": len(scores),
            "toReview": len(review),
        },
        "fields": fields,
        "review": review,
    }
