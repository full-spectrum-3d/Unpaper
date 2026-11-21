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

PAGE_TITLE = "Przedmiot wniosku"  # ostateczny fallback, gdy tytułu nie da się wyprowadzić
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
# Wyraźna lista załączników blankietu: trafia do sekcji „Załączniki”.
_ATTACHMENTS = re.compile(
    r"(?i)^(\d+\.\s*)?(załączniki|do wniosku (dołączam|załączam)|dołączam|załączam)\b"
)
# „W załączeniu:” wylicza pliki do sprawy: każdy zostaje polem pliku w sekcji przedmiotu.
_INLINE_ATTACHMENTS = re.compile(r"(?i)^(\d+\.\s*)?w załączeniu\b")
_SUBJECT_OF = re.compile(r"(?i)^\S+\s+(?:o|w sprawie|w przedmiocie)\s+(.{3,})$")
# Opcje do zaznaczenia: symbol pola wyboru albo numer pod wprowadzeniem „…proszę:”.
_CHECK_MARK = re.compile(r"^\s*(?:[☐□■▢○◯]|\[\s?[xX]?\s?\]|\(\s?\))\s*")
_CHOICE_INTRO = re.compile(r"(?i)(proszę|wybierz|zaznacz|wskaż|właściw\w+)\W*$")
_MULTI_CHOICE = re.compile(
    r"(?i)jedn\w+ lub więcej|wiele|kilka|wszystkie|więcej niż jedn|co najmniej jedn"
)
_INTRO_TAIL = frozenset({"proszę", "zaznacz", "wybierz", "wskaż", "właściwe", "właściwą"})
_NUMBER_TAIL = re.compile(r"(?i)^(.*\S)\s+(?:nr|numer)\.?$")
_GENITIVES = {"rachunek": "rachunku"}
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
    options: list[str] = field(default_factory=list)
    # Pole widoczne tylko po wybraniu opcji: (pole wyboru, wartość).
    condition: tuple[_Field, str] | None = None


@dataclass
class _Section:
    title: str
    fields: list[_Field] = field(default_factory=list)


@dataclass
class _State:
    sections: list[_Section] = field(default_factory=list)
    section_title: str = DEFAULT_SECTION
    previous_text: str = ""
    # Pole z końca poprzedniego bloku: wykropkowanie zawinięte do następnego wiersza je kontynuuje.
    carry: _Field | None = None

    def add(self, item: _Field) -> None:
        if not self.sections or self.sections[-1].title != self.section_title:
            self.sections.append(_Section(self.section_title))
        self.sections[-1].fields.append(item)


def rule_draft(doc: DocumentModel) -> FormDraft | None:
    """Szkic z wykropkowań dokumentu albo None, gdy nie ma żadnego pola przedmiotu."""
    blocks = [block for _, block in doc.iter_content_blocks()]
    title, title_end = _find_title(blocks)
    authority_kind, authority_name = _find_authority(blocks)
    attachments, file_items, attachment_blocks = find_attachments(blocks)
    page_title = _subject_title(title) or PAGE_TITLE

    state = _State(section_title=_subject_title(title) or DEFAULT_SECTION)
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
        group = _choice_group(blocks, i - 1, state.previous_text)
        if group is not None:
            i = _add_choice(group, state)
            continue
        if not has_fill(block):
            state.previous_text = text
            continue
        i = _add_fields(block, blocks, i, state)

    sections = [s for s in state.sections if s.fields]
    if sections:
        # Pliki wymienione w treści wniosku zostają przy przedmiocie sprawy, nie w „Załącznikach”.
        sections += [_Section(name, [_Field(name, "file")]) for name in file_items]
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
    ids = {id(item): f"f{n}" for n, item in enumerate(_all_fields(sections), 1)}
    page_sections: list[dict[str, Any]] = []
    for section in sections:
        fields = []
        for item in section.fields:
            kind = "long_text" if item.lines > 1 and item.kind == "short_text" else item.kind
            raw: dict[str, Any] = {
                "id": ids[id(item)],
                "label": item.label,
                "kind": kind,
                "required": kind != "file",
            }
            if item.options:
                raw["options"] = item.options
            if item.condition:
                parent, value = item.condition
                raw["visible_when"] = [
                    {"field_id": ids[id(parent)], "op": "equals", "value": value}
                ]
            fields.append(raw)
        page_sections.append({"title": section.title, "repeating": False, "fields": fields})
    return FormDraft.model_validate(
        {
            "title": title,
            "authority_kind": authority_kind,
            "authority_name": authority_name,
            "applicant_kinds": kinds,
            "attachments": attachments,
            "statements": [],
            "subject_pages": [{"title": page_title, "sections": page_sections}],
        }
    )


def _all_fields(sections: list[_Section]) -> list[_Field]:
    return [item for section in sections for item in section.fields]


def _subject_title(title: str) -> str:
    """Tytuł strony przedmiotu z tytułu wniosku: część po „o ” („Stwierdzenie nadpłaty podatku”)."""
    match = _SUBJECT_OF.match(_FOOTNOTE.sub("", title).strip())
    if not match:
        return ""
    text = match.group(1).strip(" :;,.")
    if text.isupper():
        text = text.lower()
    return text[:1].upper() + text[1:]


@dataclass
class _Option:
    text: str  # treść opcji bez symbolu i bez pola do wpisania
    field_label: str = ""  # etykieta pola do wpisania przy opcji; pusta = brak pola
    lines: int = 1


@dataclass
class _ChoiceGroup:
    intro: str
    options: list[_Option]
    end: int  # indeks pierwszego bloku za grupą


def _option_text(block: Block, numbered: bool) -> str | None:
    """Treść linii-opcji (z polem do wpisania włącznie) albo None, gdy to nie opcja."""
    raw = block.text
    mark = _CHECK_MARK.match(raw)
    if mark:
        return raw[mark.end() :]
    if block.kind == "checkbox_option":
        return raw
    if numbered:
        match = _NUMBERING.match(raw)
        if match and match.group(1)[0].isdigit():
            return raw[match.end() :]
    return None


def _choice_group(blocks: list[Block], start: int, intro: str) -> _ChoiceGroup | None:
    """Kolejne linie-opcje od `start` jako jedna grupa wyboru (min. 2 opcje) albo None."""
    numbered = bool(_CHOICE_INTRO.search(intro.rstrip(":")) and intro.endswith(":"))
    options: list[_Option] = []
    j = start
    while j < len(blocks):
        text = _option_text(blocks[j], numbered)
        if text is None:
            break
        j += 1
        option = _parse_option(text)
        if option.field_label:
            # Dalsze wykropkowane linie to ciąg dalszy tego samego pola.
            while j < len(blocks) and _is_pure_placeholder(blocks[j]):
                j += 1
        else:
            label, after = _following_field(blocks, j, option.text)
            if label:
                option.field_label, j = label, after
        options.append(option)
    if len(options) < 2:
        return None
    return _ChoiceGroup(intro, options, j)


def _parse_option(text: str) -> _Option:
    before = _FILL_SPLIT.split(text)[0]
    has_inline = len(_FILL_SPLIT.split(text)) > 1
    label_text = clean_text(before).strip(" :;,-")
    if not has_inline:
        return _Option(_option_label(label_text))
    number = _NUMBER_TAIL.match(label_text)
    if number:
        head = number.group(1)
        noun = head.split()[-1].casefold()
        return _Option(_option_label(head), f"Numer {_GENITIVES.get(noun, noun)}")
    if label_text.casefold().endswith("z tytułu"):
        return _Option(_option_label(label_text[: -len("z tytułu")]), "Tytuł")
    option = _option_label(label_text)
    return _Option(option, option)


def _option_label(text: str) -> str:
    text = _FOOTNOTE.sub("", text).strip(" :;,-.")
    return text[:1].upper() + text[1:]


def _following_field(blocks: list[Block], i: int, option: str) -> tuple[str, int]:
    """Pole bez opisu zaraz pod opcją (wykropkowanie albo tabela): etykieta i indeks za nim."""
    if i >= len(blocks):
        return "", i
    block = blocks[i]
    if block.kind == "table":
        i += 1
        while i < len(blocks) and blocks[i].kind == "table_cell":
            i += 1
    elif _is_pure_placeholder(block):
        i += 1
        while i < len(blocks) and _is_pure_placeholder(blocks[i]):
            i += 1
    else:
        return "", i
    label, after = _label_after(blocks, i)
    if label:
        return label, after
    last = option.split()[-1].casefold() if option else ""
    if last in _GENITIVES or last in _GENITIVES.values():
        return f"Numer {_GENITIVES.get(last, last)}", i
    return option, i


def _choice_label(intro: str) -> str:
    words = clean_text(intro).strip(" :;,-").split()
    while len(words) > 1 and words[-1].casefold().strip(":") in _INTRO_TAIL:
        words.pop()
    label = _clean_label(" ".join(words))
    return label or "Wybierz opcję"


def _add_choice(group: _ChoiceGroup, state: _State) -> int:
    """Pole wyboru z opcji i pola zależne od opcji, przy których jest miejsce na wpis."""
    texts = " ".join([group.intro, *(o.text for o in group.options)])
    kind = "multi_choice" if _MULTI_CHOICE.search(texts) else "single_choice"
    choice = _Field(
        _choice_label(group.intro), kind, options=[o.text for o in group.options if o.text]
    )
    state.add(choice)
    for option in group.options:
        if option.field_label:
            state.add(
                _Field(
                    option.field_label, _kind(option.field_label), condition=(choice, option.text)
                )
            )
    state.previous_text = ""
    return group.end


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
    carry, state.carry = state.carry, None
    for k, segment in enumerate(segments[:-1]):
        label = _clean_label(segment)
        if k == 0 and not label and carry is not None:
            # Ciąg dalszy wykropkowania z poprzedniego wiersza: opis pod nim nazywa tamto pole.
            described, i = _label_after(blocks, i)
            if described:
                carry.label, carry.kind = described, _kind(described)
            continue
        if label and set(label.casefold().split()) <= _CONNECTORS and labels:
            label = f"{labels[-1]} {label.casefold()}"
        if not label and k == 0:
            label, i = _label_after(blocks, i)
        if not label:
            continue
        labels.append(label)
        state.add(_Field(label, _kind(label)))
    if labels and not clean_text(segments[-1]) and not segments[-1].strip(" .…_"):
        state.carry = state.sections[-1].fields[-1]
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


def find_attachments(blocks: list[Block]) -> tuple[list[str], list[str], set[int]]:
    """Listy pod „Załączniki:” (załączniki blankietu) i „W załączeniu:” (pliki do sprawy).

    Zwraca (załączniki, pliki przedmiotu, id bloków z list - to nie pola).
    """
    attachments: list[str] = []
    files: list[str] = []
    used: set[int] = set()
    seen: set[str] = set()
    for i, block in enumerate(blocks):
        text = clean_text(block.text)
        if id(block) in used or not (_ATTACHMENTS.match(text) or _INLINE_ATTACHMENTS.match(text)):
            continue
        target = attachments if _ATTACHMENTS.match(text) else files
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
            name = text[:1].upper() + text[1:]
            if text and name not in seen:
                seen.add(name)
                target.append(name)
    return attachments, files, used
