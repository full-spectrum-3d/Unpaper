"""Szkic formularza z reguł, bez LLM: zapasowy wynik, gdy model zawiedzie.

Pole to miejsce wykropkowane w dokumencie, a etykieta to tekst przed nim albo opis
w nawiasie pod nim. Typ wynika z etykiety, sekcja z ostatniego nagłówka. Nagłówek
blankietu (wszystko przed tytułem „WNIOSEK…”) pomijamy: są tam dane wnioskodawcy,
data i adresat, które dają sekcje predefiniowane. Wynik przechodzi tę samą
normalizację co szkic modelu (usuwa m.in. pola wnioskodawcy i podpis).

Etykiety bywają niezgrabne („W miejscowości”), dlatego szkic z reguł zawsze ma
ostrzeżenie `W24_RULE_BASED_DRAFT`. To i tak więcej niż pusty szkielet formularza.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.document import Block, DocumentModel
from app.models.draft import FormDraft
from app.pipeline.draft_rules import clean_text, has_fill

PAGE_TITLE = "Przedmiot wniosku"
DEFAULT_SECTION = "Dane wniosku"
MAX_LABEL_WORDS = 6
MAX_LABEL_BLOCK_CHARS = 120
MAX_TITLE_PARTS = 3
MAX_ATTACHMENTS = 15

_FILL_SPLIT = re.compile(r"[.…_]{3,}|\[POLE\]")
_PAREN_LABEL = re.compile(r"^\s*[(/]\s*([^()/]{2,}?)\s*[)/]{1,2}")
_NUMBERING = re.compile(r"^\s*(\d{1,2}(\.\d{1,2})*[.)]|[a-z][.)/])(\s+|$)")
_FOOTNOTE = re.compile(r"(?<=\w)\d\)|\*+")
_TITLE = re.compile(r"(?i)^(wniosek|zgłoszenie|deklaracja|oświadczenie)\b")
_ORGAN = re.compile(
    r"\b(Wójt|Burmistrz|Prezydent|Starosta|Marszałek)(\s+[A-ZĄĆĘŁŃÓŚŹŻ][\w-]*){1,4}"
)
_ORGAN_UPPER = re.compile(r"^(WÓJT|BURMISTRZ|PREZYDENT|STAROSTA|MARSZAŁEK)\b[\w\s-]{3,60}$")
_OFFICE = re.compile(r"^(Urząd|URZĄD|Starostwo|STAROSTWO)\b[\w\s-]{3,60}$")
_PLACE = re.compile(r"^[A-ZĄĆĘŁŃÓŚŹŻ][\w-]+(\s[A-ZĄĆĘŁŃÓŚŹŻ][\w-]+){0,2}$")
_ATTACHMENTS = re.compile(r"(?i)^(\d+\.\s*)?(załączniki|w załączeniu)\b")
_COMPANY = re.compile(
    r"(?i)nazwa firmy|/\s*nazwa|nazwa wnioskodawcy|siedzib|\bNIP\b|\bREGON\b|\bKRS\b"
)
_CONNECTORS = frozenset({"od", "do", "i", "oraz", "lub", "z", "w", "we", "na", "przy", "tj."})
_UNITS = frozenset({"cm", "m", "m2", "m²", "zł", "dni", "ha", "szt", "szt.", "kg", "osób"})

_DATE = re.compile(r"(?i)\bdat[aąy]\b|\bdnia\b|\btermin")
_NUMBER = re.compile(
    r"(?i)kwot|kwoc|liczb|ilość|powierzchni|\bm2\b|\bzł\b|\bdni\b|\bcm\b|wysokoś|\(m2\)"
)
_LONG = re.compile(r"(?i)uzasadnien|\bopis|osiągnię|opini|dodatkowe informacje")


@dataclass
class _Field:
    label: str
    kind: str = "short_text"
    lines: int = 1


@dataclass
class _Section:
    title: str
    fields: list[_Field] = field(default_factory=list)


@dataclass
class _State:
    sections: list[_Section] = field(default_factory=list)
    section_title: str = DEFAULT_SECTION
    previous_text: str = ""

    def add(self, item: _Field) -> None:
        if not self.sections or self.sections[-1].title != self.section_title:
            self.sections.append(_Section(self.section_title))
        self.sections[-1].fields.append(item)


def rule_draft(doc: DocumentModel) -> FormDraft | None:
    """Szkic z wykropkowań dokumentu albo None, gdy nie ma żadnego pola przedmiotu."""
    blocks = [block for _, block in doc.iter_content_blocks()]
    title, title_end = _find_title(blocks)
    authority_kind, authority_name = _find_authority(blocks)
    attachments, attachment_blocks = _find_attachments(blocks)

    state = _State()
    i = title_end
    while i < len(blocks):
        block = blocks[i]
        i += 1
        if id(block) in attachment_blocks:
            continue
        text = clean_text(block.text)
        if block.kind == "heading" and not has_fill(block) and not _PAREN_LABEL.match(text):
            state.section_title = _section_title(text) or state.section_title
            state.previous_text = ""
            continue
        if not has_fill(block):
            state.previous_text = text
            continue
        i = _add_fields(block, blocks, i, state)

    sections = [s for s in state.sections if s.fields]
    if not sections:
        return None
    full_text = " ".join(b.text for b in blocks)
    kinds = (
        ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"]
        if _COMPANY.search(full_text)
        else [
            "SELF",
            "OTHER_PERSON",
        ]
    )
    counter = 0
    page_sections: list[dict[str, Any]] = []
    for section in sections:
        fields = []
        for item in section.fields:
            counter += 1
            kind = "long_text" if item.lines > 1 and item.kind == "short_text" else item.kind
            fields.append(
                {"id": f"f{counter}", "label": item.label, "kind": kind, "required": True}
            )
        page_sections.append({"title": section.title, "repeating": False, "fields": fields})
    return FormDraft.model_validate(
        {
            "title": title,
            "authority_kind": authority_kind,
            "authority_name": authority_name,
            "applicant_kinds": kinds,
            "attachments": attachments,
            "statements": [],
            "subject_pages": [{"title": PAGE_TITLE, "sections": page_sections}],
        }
    )


def _add_fields(block: Block, blocks: list[Block], i: int, state: _State) -> int:
    """Pola z bloku z wykropkowaniem; zwraca indeks następnego nieprzetworzonego bloku."""
    text = clean_text(block.text)
    pure = block.kind == "input_placeholder" or not text
    if pure:
        label, i = _label_after(blocks, i)
        if not label and state.previous_text.endswith(":"):
            label = _clean_label(state.previous_text)
        state.previous_text = ""
        if not label:
            return i
        item = _Field(label, _kind(label))
        while i < len(blocks) and _is_pure_placeholder(blocks[i]):
            item.lines += 1
            i += 1
        state.add(item)
        return i

    segments = _FILL_SPLIT.split(block.text)
    labels: list[str] = []
    for k, segment in enumerate(segments[:-1]):
        label = _clean_label(segment)
        if label and set(label.casefold().split()) <= _CONNECTORS and labels:
            label = f"{labels[-1]} {label.casefold()}"
        if not label and k == 0:
            label, i = _label_after(blocks, i)
        if not label:
            continue
        labels.append(label)
        state.add(_Field(label, _kind(label)))
    unit = clean_text(segments[-1]).strip(" .,")
    if labels and unit in _UNITS:
        last = state.sections[-1].fields[-1]
        last.label, last.kind = f"{last.label} ({unit})", "number"
    state.previous_text = ""
    return i


def _label_after(blocks: list[Block], i: int) -> tuple[str, int]:
    """Opis pola pod wykropkowaniem: „(imię i nazwisko)”, „/ adres /” albo blok `label`."""
    if i >= len(blocks) or has_fill(blocks[i]):
        return "", i
    text = clean_text(blocks[i].text)
    match = _PAREN_LABEL.match(text)
    if match:
        return _clean_label(match.group(1)), i + 1
    if blocks[i].kind == "label" and len(text) <= MAX_LABEL_BLOCK_CHARS:
        return _clean_label(text), i + 1
    return "", i


def _is_pure_placeholder(block: Block) -> bool:
    return block.kind == "input_placeholder" or (has_fill(block) and not clean_text(block.text))


def _clean_label(text: str) -> str:
    text = _FOOTNOTE.sub("", clean_text(text))
    text = re.split(r"[.;]\s|,\s(?=\w+$)", text.strip(" :;,-"))[-1]
    text = _NUMBERING.sub("", text).strip(" :;,-\u2013()/")
    words = text.split()
    if len(words) > MAX_LABEL_WORDS:
        words = words[-MAX_LABEL_WORDS:]
    while len(words) > 1 and words[-1].casefold() in _CONNECTORS:
        words.pop()
    label = " ".join(words)
    return label[:1].upper() + label[1:] if label else ""


def _kind(label: str) -> str:
    if _DATE.search(label):
        return "date"
    if _NUMBER.search(label):
        return "number"
    if _LONG.search(label):
        return "long_text"
    return "short_text"


def _section_title(text: str) -> str:
    text = _NUMBERING.sub("", _FOOTNOTE.sub("", text)).strip(" :□☐-")
    if text.isupper():
        text = text.capitalize()
    return text


def _find_title(blocks: list[Block]) -> tuple[str, int]:
    """Tytuł wniosku i indeks bloku za nim. „WNIOSEK” + „o wydanie…” łączymy w jeden tytuł."""
    for i, block in enumerate(blocks):
        text = clean_text(block.text)
        if block.kind != "heading" or not _TITLE.match(text) or has_fill(block):
            continue
        parts = [text]
        j = i + 1
        if len(text.split()) == 1:
            while j < len(blocks) and len(parts) <= MAX_TITLE_PARTS:
                nxt = blocks[j]
                nxt_text = clean_text(nxt.text)
                if nxt.kind == "heading" or has_fill(nxt) or len(nxt_text) > MAX_LABEL_BLOCK_CHARS:
                    break
                parts.append(nxt_text)
                j += 1
        title = _FOOTNOTE.sub("", " ".join(parts)).strip()
        first, _, rest = title.partition(" ")
        title = (
            f"{first.capitalize()} {rest}".strip() if first.isupper() and rest.islower() else title
        )
        return title, j
    return "Wniosek", 0


def _find_authority(blocks: list[Block]) -> tuple[str, str]:
    for i, block in enumerate(blocks):
        text = clean_text(block.text)
        if _ORGAN_UPPER.match(text):
            return "ORGAN", " ".join(w.capitalize() for w in text.split())
        match = _ORGAN.search(text)
        if match:
            return "ORGAN", match.group(0)
        if _OFFICE.match(text):
            name = " ".join(w.capitalize() for w in text.split()) if text.isupper() else text
            nxt = clean_text(blocks[i + 1].text) if i + 1 < len(blocks) else ""
            if len(name.split()) <= 2 and _PLACE.match(nxt):
                name = f"{name} {nxt}"
            return "URZAD", name
    return "URZAD", "Urząd"


def _find_attachments(blocks: list[Block]) -> tuple[list[str], set[int]]:
    """Pozycje listy pod „Załączniki:” / „W załączeniu:” i id ich bloków (to nie pola)."""
    items: list[str] = []
    used: set[int] = set()
    for i, block in enumerate(blocks):
        if not _ATTACHMENTS.match(clean_text(block.text)):
            continue
        used.add(id(block))
        for item in blocks[i + 1 : i + 1 + MAX_ATTACHMENTS]:
            text = _NUMBERING.sub("", clean_text(item.text)).strip(" ;,.")
            numbered = bool(_NUMBERING.match(item.text))
            if (
                item.kind == "heading"
                or len(text) > 300
                or _PAREN_LABEL.match(text)
                or (_is_pure_placeholder(item) and not numbered)
            ):
                break
            used.add(id(item))
            if text and text not in items:
                items.append(text[:1].upper() + text[1:])
        break
    return items, used
