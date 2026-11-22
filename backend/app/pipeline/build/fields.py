"""Mapowanie typów pól, walidatorów i generowanie techName (spec §8.3, §7.2)."""

import re
import unicodedata
from collections.abc import Mapping

from app.models.draft import CHOICE_KINDS, DraftField, FieldKind
from app.models.draft import Condition as DraftCondition
from app.models.form import ALLOWED_VALIDATORS, CHOICE_TYPES, FieldType, Validator
from app.models.warning import ConversionWarning
from app.pipeline.build.file_hints import file_constraints_html
from app.pipeline.build.html import paragraphs
from app.pipeline.build.ir import AllOf, Condition, Eq, FieldNode, Not, PageNode, Semantic
from app.pipeline.issues import IssueCode

_TRANSLITERATION = str.maketrans("ąćęłńóśźż", "acelnoszz")
_TITLE_PREFIXES = ("wniosek", "zgłoszenie", "deklaracja", "oświadczenie")
_TITLE_MAX = 255
_LABEL_MAX = 80
_TECH_NAME_MAX = 60
_RADIO_MAX_OPTIONS = 5
_SEARCH_THRESHOLD = 15

# Odwołania do przepisów w tytule (standard: tytuł krótki, bez przepisów). Tylko wyraźne wzorce.
_INTRO = r"(?:na\s+podstawie|zgodnie\s+z|o\s+kt[óo]r(?:ym|ej|ych)\s+mowa\s+w)"
_ARTICLE = r"art\.\s*\d+\w*(?:\s*(?:ust\.|pkt|lit\.|§)\s*\d+\w*)*"
_STATUTE = (
    r"(?:\s+(?:ustawy|rozporządzenia)\s+z\s+dnia\s+\d{1,2}\s+\w+\s+\d{4}\s*r\.?"
    r"(?:\s+[^,;()]*)?"  # tytuł ustawy aż do przecinka lub końca
    r"|\s+(?:ustawy|Ordynacji\s+podatkowej|Kodeksu\s+\w+(?:\s+\w+)?))?"
)
_DZ_U = r"Dz\.\s*U\.[^()]*"
_LEGAL_REFERENCES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"\s*\(\s*(?:t\.\s*j\.\s*)?{_DZ_U}\)",
        rf"\s*\(\s*{_INTRO}\s+{_ARTICLE}{_STATUTE}[^()]*\)",
        rf"[,\s]*{_INTRO}\s+{_ARTICLE}{_STATUTE}",
        r"[,\s]*Dz\.\s*U\.\s*(?:z\s+\d{4}\s*r\.?\s*)?(?:Nr\s*\d+\s*)?,?\s*poz\.\s*\d+"
        r"(?:\s+z\s+późn\.\s*zm\.)?",
    )
)

_KIND_TYPES: dict[FieldKind, FieldType] = {
    "short_text": FieldType.TEXT_FIELD,
    "long_text": FieldType.TEXTAREA,
    "number": FieldType.NUMBER,
    "date": FieldType.DATEPICKER,
    "file": FieldType.FILE_UPLOADER,
}

_AMOUNT_LABEL = re.compile(
    r"^\s*(kwot[aęy]|wysokość|należnoś\w*|wartość|sum[ay]|razem|łączn\w*|ogółem)\b"
    r"|\b(zł|pln)\b",
    re.IGNORECASE,
)
_NOT_AMOUNT = re.compile(r"słownie|rachunk|numer|nazwa|tytuł", re.IGNORECASE)
"""Kwota słownie, numer rachunku, tytuł płatności: tekst, mimo słowa „kwota” lub „zł”."""

_SEMANTIC_VALIDATORS: dict[Semantic, Validator] = {
    Semantic.PESEL: Validator.PESEL,
    Semantic.NIP: Validator.NIP,
    Semantic.REGON: Validator.REGON,
    Semantic.ZIP_CODE: Validator.ZIP_CODE,
    Semantic.EMAIL: Validator.EMAIL,
    Semantic.EPUAP: Validator.EPUAP,
    Semantic.ADE: Validator.ADE,
    Semantic.ID_CARD: Validator.SERIAL_NUMBER_ID_CARD,
}

_LABEL_SEMANTICS: tuple[tuple[re.Pattern[str], Semantic], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), semantic)
    for pattern, semantic in (
        (r"\bpesel\b", Semantic.PESEL),
        (r"\bnip\b", Semantic.NIP),
        (r"\bregon\b", Semantic.REGON),
        (r"kod\w*\s+pocztow", Semantic.ZIP_CODE),
        (r"e-?mail|poczty\s+elektronicznej", Semantic.EMAIL),
        (r"\bepuap\b", Semantic.EPUAP),
        (r"e-?doręcze", Semantic.ADE),
        (r"seri\w*\s+i\s+numer\w*\s+dowodu", Semantic.ID_CARD),
        (r"numer\w*\s+kierunkow", Semantic.PHONE_PREFIX),
        # Jednostki adresowe tylko jako cała etykieta („Powiat grodzki” to nie słownik).
        # Miejscowość zostaje tekstem: tak ma wzorzec COI („Lokalizacja budynku”).
        (r"^\s*województwo\s*[:*]?\s*$", Semantic.VOIVODESHIP),
        (r"^\s*powiat\s*[:*]?\s*$", Semantic.COUNTY),
        (r"^\s*gmina\s*[:*]?\s*$", Semantic.COMMUNE),
        (r"\bkraj\b|\bpaństw|obywatelstw", Semantic.COUNTRY),
    )
)


_IDENTIFIERS = frozenset({Semantic.PESEL, Semantic.NIP, Semantic.REGON})
"""Identyfikatory o własnym walidatorze formatu: wspólne pole („NIP/REGON”) nie może mieć
żadnego z nich, bo walidator jednego odrzuciłby poprawną wartość drugiego."""


def label_semantic(label: str) -> Semantic | None:
    """Pierwsza semantyka, której wzorzec pasuje do etykiety; `None` dla pola na kilka
    identyfikatorów naraz („NIP/REGON”, „PESEL lub NIP”)."""
    matched = [sem for rx, sem in _LABEL_SEMANTICS if rx.search(label)]
    if len(_IDENTIFIERS.intersection(matched)) > 1:
        return None
    return matched[0] if matched else None


def slugify(text: str, *, max_length: int = 60) -> str:
    """techName: ASCII `[a-z0-9_]`, polskie znaki transliterowane."""
    lowered = text.lower().translate(_TRANSLITERATION)
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    if len(slug) > max_length:
        cut = slug[:max_length]
        idx = cut.rfind("_")
        if idx >= max_length / 2:
            cut = cut[:idx]
        slug = cut.strip("_")
    return slug or "pole"


def _strip_legal_references(title: str) -> str:
    """Usuwa odwołania do przepisów i sprząta po nich interpunkcję."""
    for rx in _LEGAL_REFERENCES:
        title = rx.sub("", title)
    title = re.sub(r"\(\s*\)", "", title)
    title = re.sub(r"\s+([,;.])", r"\1", title)
    return " ".join(title.split()).rstrip(" ,;:-–")  # noqa: RUF001


def normalize_title(raw: str) -> tuple[str, list[ConversionWarning]]:
    """Zwija białe znaki, usuwa odwołania do przepisów, ucina do 255 znaków, pilnuje prefiksu."""
    issues: list[ConversionWarning] = []
    title = " ".join(raw.split())
    cleaned = _strip_legal_references(title)
    if cleaned and cleaned != title:
        title = cleaned
        issues.append(
            ConversionWarning(
                code=IssueCode.W31_TITLE_LEGAL_REFERENCE,
                message="Z tytułu usunięto odwołanie do przepisów.",
            )
        )
    if len(title) > _TITLE_MAX:
        title = title[:_TITLE_MAX].rstrip()
        issues.append(
            ConversionWarning(
                code=IssueCode.W08_TITLE_TRUNCATED, message="Tytuł skrócono do 255 znaków."
            )
        )
    if not title:
        title = "Wniosek"
        issues.append(
            ConversionWarning(
                code=IssueCode.W05_TITLE_PREFIX, message="Brak tytułu, użyto „Wniosek”."
            )
        )
    elif not title.lower().startswith(_TITLE_PREFIXES):
        issues.append(
            ConversionWarning(
                code=IssueCode.W05_TITLE_PREFIX,
                message=(
                    "Tytuł nie zaczyna się od „Wniosek”, „Zgłoszenie”, „Deklaracja” "
                    "ani „Oświadczenie”."
                ),
            )
        )
    return title, issues


def _choice_type(draft: DraftField, key: str, issues: list[ConversionWarning]) -> FieldType:
    count = len(draft.options)
    if draft.kind == "single_choice":
        if count == 0 or count == 1:
            issues.append(
                ConversionWarning(
                    code=IssueCode.W07_CHOICE_OPTIONS,
                    message=f"Pole wyboru ma {count} opcji.",
                    path=key,
                )
            )
            return FieldType.TEXT_FIELD if count == 0 else FieldType.CHECKBOX
        return FieldType.RADIO if count <= _RADIO_MAX_OPTIONS else FieldType.SELECT
    if count == 0:
        issues.append(
            ConversionWarning(
                code=IssueCode.W07_CHOICE_OPTIONS, message="Pole wyboru nie ma opcji.", path=key
            )
        )
        return FieldType.TEXT_FIELD
    return FieldType.CHECKBOX


def _validators(
    required: bool, semantic: Semantic | None, field_type: FieldType
) -> list[Validator]:
    allowed = ALLOWED_VALIDATORS[field_type]
    result: list[Validator] = []
    if required and Validator.REQUIRED in allowed:
        result.append(Validator.REQUIRED)
    if field_type is not FieldType.TEXT_FIELD or semantic is None:
        return result
    extra = _SEMANTIC_VALIDATORS.get(semantic)
    if extra is not None and extra not in result:
        result.append(extra)
    return result


def map_draft_field(field: DraftField, *, key: str) -> tuple[FieldNode, list[ConversionWarning]]:
    """Pole ze szkicu na `FieldNode` (spec §8.3). Semantykę ustala etykieta."""
    issues: list[ConversionWarning] = []
    unique = list(dict.fromkeys(field.options))
    if len(unique) != len(field.options):
        field = field.model_copy(update={"options": unique})
        issues.append(
            ConversionWarning(
                code=IssueCode.W07_CHOICE_OPTIONS,
                message="Usunięto powtórzone opcje pola.",
                path=key,
            )
        )
    node = FieldNode(
        key=key,
        type=FieldType.TEXT_FIELD,
        title=field.label,
        tech_name=slugify(field.label),
    )
    if field.kind == "info":
        node.type = FieldType.TEXT_BLOCK
        node.title = ""
        node.description_html = paragraphs(field.label)
        return node, issues

    if field.kind in CHOICE_KINDS:
        node.type = _choice_type(field, key, issues)
        if node.type in (FieldType.RADIO, FieldType.SELECT, FieldType.CHECKBOX):
            node.options = list(field.options)
        if node.type is FieldType.SELECT and len(field.options) > _SEARCH_THRESHOLD:
            node.search_enabled = True
    else:
        node.type = _KIND_TYPES[field.kind]

    if len(field.label) > _LABEL_MAX:
        issues.append(
            ConversionWarning(
                code=IssueCode.W02_LABEL_TOO_LONG,
                message=f"Etykieta ma {len(field.label)} znaków.",
                path=key,
            )
        )
    if field.kind == "file":
        node.description_html = file_constraints_html()
    else:
        node.semantic = label_semantic(field.label)
    # Typ z etykiety wygrywa ze szkicem LLM: kod pocztowy/PESEL jako NUMBER traci walidator
    # formatu (NUMBER dopuszcza tylko REQUIRED), a kwota jako tekst przyjmuje dowolny napis.
    if node.type is FieldType.NUMBER and node.semantic in _SEMANTIC_VALIDATORS:
        node.type = FieldType.TEXT_FIELD
    elif (
        node.type is FieldType.TEXT_FIELD
        and node.semantic is None
        and _AMOUNT_LABEL.search(field.label)
        and not _NOT_AMOUNT.search(field.label)
    ):
        node.type = FieldType.NUMBER
    node.validation = _validators(field.required, node.semantic, node.type)
    return node, issues


def unresolved_condition(
    conds: list[DraftCondition], by_id: Mapping[str, FieldNode], owner: FieldNode
) -> DraftCondition | None:
    """Pierwszy warunek, którego cel nie istnieje, nie jest wyborem albo jest właścicielem."""
    for cond in conds:
        target = by_id.get(cond.field_id)
        if target is None or target is owner or target.type not in CHOICE_TYPES:
            return cond
    return None


def convert_conditions(
    conds: list[DraftCondition], by_id: Mapping[str, FieldNode], owner: FieldNode
) -> Condition | None:
    """Warunki szkicu (AND) na `Condition`. `None`, gdy któreś pole jest nieznane,
    nie jest polem wyboru albo jest samym właścicielem."""
    if unresolved_condition(conds, by_id, owner) is not None:
        return None
    items: list[Condition] = []
    for cond in conds:
        target = by_id[cond.field_id]
        eq = Eq(target.key, cond.value)
        items.append(Not(eq) if cond.op == "not_equals" else eq)
    if not items:
        return None
    return items[0] if len(items) == 1 else AllOf(tuple(items))


def assign_unique_tech_names(pages: list[PageNode]) -> None:
    """Pierwsze wystąpienie zostaje, kolejne dostają `_2`, `_3`. Sekcje i pola wspólnie."""
    used: set[str] = set()

    def unique(base: str) -> str:
        if base not in used:
            used.add(base)
            return base
        n = 2
        while True:
            suffix = f"_{n}"
            name = base[: _TECH_NAME_MAX - len(suffix)].rstrip("_") + suffix
            if name not in used:
                break
            n += 1
        used.add(name)
        return name

    for page in pages:
        for section in page.sections:
            section.tech_name = unique(section.tech_name)
            for node in section.fields:
                node.tech_name = unique(node.tech_name)
