"""Podpowiedzi w dokumencie przed analizą: listy wyboru, których ekstrakcja nie oznaczyła.

Kratki (☐) na blankietach bywają rysowane (PDF), wstawiane jako punktory listy
w czcionce Wingdings (DOCX) albo w ogóle pominięte. Wtedy model widzi zwykłe linie
tekstu i robi z każdego wariantu osobne pole (projekt LLM §9.2, błąd 1). Ten moduł
oznacza takie linie jako `checkbox_option`, więc w prompcie stają się `[OPCJA]`:

- znaki kratek w tekście („❑ pies ❑ suka”) → osobne opcje;
- „TAK NIE” na końcu linii → opcje Tak / Nie;
- lista po wstępie, który zapowiada wybór: „Proszę o wydanie zaświadczenia o:*”,
  „(postaw „x” w wybranym polu)”, „(zaznaczyć właściwą kratkę)”, „Rodzaje wniosków:”;
- opcje numerowane w jednej linii („1. właściciel 2. najemca 3. …”) → osobne opcje.

Osobno numerowane pozycje deklaracji („26. Miejscowość”, „27. Ulica”) bez wykropkowania
(kratki do wpisania są rysowane) dostają znacznik `[POLE]`, żeby model nie wziął ich
za nagłówki albo zwykły tekst.

Wstęp do oświadczeń i do listy załączników nie zapowiada wyboru. Moduł nie zmienia
treści, tylko rodzaj bloków (i dzieli bloki z kilkoma opcjami) oraz dokleja `[POLE]`,
więc błąd tutaj najwyżej pogarsza podpowiedź dla modelu.
"""

import re

from app.models.document import FIELD_MARKER, Block, DocumentModel
from app.pipeline.draft_rules import clean_text, has_fill

MIN_OPTIONS = 2
MAX_OPTIONS = 25
MAX_OPTION_CHARS = 200
MAX_SHORT_OPTION_CHARS = 40  # lista bez słowa „wybierz” itp.: tylko krótkie pozycje
MIN_SHORT_OPTIONS = 3
MAX_OTHER_PREFIX_CHARS = 40  # „inne ……” jako ostatnia opcja z polem do wpisania

# Kratki: znaki Unicode, znaki Wingdings z DOCX/PDF (obszar prywatny U+F0xx) i „[ ]” z OCR.
_BOX = re.compile(r"[□☐◻❑❒▢⬜\uf06f\uf0a8\uf071\uf072\uf0fe]|\[ ?\]")
_YES_NO = re.compile(r"^(?P<prefix>.*?)\s*\bTAK\s*/?\s*NIE\s*$")
# Wstęp, który jednoznacznie zapowiada wybór.
_STRONG_CUE = re.compile(
    r"(?i)\bzaznacz(yć|yc)?\b|\bpostaw(ić)?\s+\S{0,2}x\b|w wybranym polu"
    r"|właściw\w+ (kratk|pol)|\bwybierz\b|należy wybrać|niepotrzebne skreślić"
)
# Wstęp, który zapowiada wybór, gdy kończy się dwukropkiem albo pozycje są numerowane.
_WEAK_CUE = re.compile(r"(?i)\bproszę\b|\bwnoszę\b|\brodzaj|\bspos[óo]b|\bform[aęy]\b|\btryb\b")
_COLON_END = re.compile(r"(\*\s*:|:\s*\*?)\s*$")
_NOT_A_CHOICE = re.compile(r"(?i)oświadcz|zobowiązuj|załącz|w załączeniu|pouczeni|objaśnieni")
_ITEM_STOP = re.compile(r"(?i)^(jeśli|jeżeli|w przypadku|uwaga|należy|do wniosku|\*)")
_NUMBER_PREFIX = re.compile(r"^\s*(\d{1,2})[.)]\s*")
_INLINE_NUMBER = re.compile(r"(?:^|\s)(\d{1,2})[.)]\s+")
_OPTION_KINDS = frozenset({"paragraph", "label", "checkbox_option"})
# Krótka lista samych etykiet pól („Wnioskodawca:” + „Imię”, „Adres”) to nie wybór,
# szczególnie w arkuszach, gdzie miejscem do wpisania jest pusta komórka, a nie kropki.
_FIELD_LABEL = re.compile(
    r"(?i)\b(imię|nazwisko|nazwa|adres|pesel|nip|regon|telefon|e-mail|data|numer|nr|"
    r"miejscowość|ulica|kod|kwota|podpis)\b"
)

# Numerowana pozycja deklaracji: „26. Miejscowość”, krótka etykieta bez dwukropka na końcu.
MAX_POSITION_WORDS = 6
_NUMBERED_POSITION = re.compile(r"^\d{1,3}\.\s+(?P<label>\S.*)$")
# Słowa tekstu informacyjnego; „…” albo „..” w etykiecie to już miejsce na wpis.
_NOT_A_POSITION = re.compile(r"(?i)\b(pouczeni|objaśnieni|informacj|uwaga)|[.…_]{2,}|…")
# Zdanie urwane w pół (instrukcja wypełniania) albo nagłówek listy załączników.
_POSITION_STOP = re.compile(r"(?i)\s(lub|i|oraz|albo|a|w|z|na|do|od|o)$|^załącznik")
_POSITION_KINDS = frozenset({"paragraph", "label"})


def annotate_choices(doc: DocumentModel) -> DocumentModel:
    """Kopia dokumentu z liniami wyboru oznaczonymi jako `checkbox_option`
    i numerowanymi pozycjami bez wykropkowania oznaczonymi jako pola."""
    pages = [
        page.model_copy(update={"blocks": _mark_positions(_annotate(page.blocks))})
        for page in doc.pages
    ]
    return doc.model_copy(update={"pages": pages})


def _mark_positions(blocks: list[Block]) -> list[Block]:
    """Dokleja `[POLE]` do numerowanych pozycji, po których nie ma od razu miejsca na wpis.

    Pozycje idą seriami („26. Miejscowość”, „27. Kod pocztowy”, „28. Ulica”). Seria musi
    się kończyć nagłówkiem, miejscem na wpis albo końcem strony. Zwykły tekst po serii to
    ciąg dalszy etykiet, czyli nagłówek kolumn tabeli („36. Liczba gospodarstw domowych
    zajmujących” | „37. Stawka” + „lokale o powierzchni do 45 m²”), a opcje po pozycji
    to pytanie wyboru - takich pozycji nie oznaczamy.
    """
    out = list(blocks)
    i = 0
    while i < len(blocks):
        end = i
        while end < len(blocks) and _is_numbered(blocks[end]):
            end += 1
        if end == i:
            i += 1
            continue
        after = blocks[end] if end < len(blocks) else None
        if after is None or after.kind == "heading" or has_fill(after):
            for k in range(i, end):
                nxt = blocks[k + 1] if k + 1 < len(blocks) else None
                if not (nxt is not None and has_fill(nxt)) and _is_position(blocks[k]):
                    text = f"{blocks[k].text.rstrip()} {FIELD_MARKER}"
                    out[k] = blocks[k].model_copy(update={"text": text})
        i = end
    return out


def _is_numbered(block: Block) -> bool:
    return (
        block.kind in _POSITION_KINDS
        and not has_fill(block)
        and bool(_NUMBERED_POSITION.match(clean_text(block.text)))
    )


def _is_position(block: Block) -> bool:
    if block.kind not in _POSITION_KINDS or has_fill(block) or FIELD_MARKER in block.text:
        return False
    match = _NUMBERED_POSITION.match(clean_text(block.text))
    if not match:
        return False
    label = match["label"]
    return (
        len(label.split()) <= MAX_POSITION_WORDS
        and not label.endswith((":", "."))
        and not label.isupper()
        and not _NOT_A_POSITION.search(label)
        and not _POSITION_STOP.search(label)
        and not _STRONG_CUE.search(label)
    )


def _annotate(blocks: list[Block]) -> list[Block]:
    split: list[Block] = []
    for block in blocks:
        split.extend(_split_marked_options(block))
    out: list[Block] = []
    i = 0
    while i < len(split):
        block = split[i]
        out.append(block)
        i += 1
        if not _is_intro(block):
            continue
        items = _list_items(split, i)
        options = _as_options(block, items)
        if options is None:
            continue
        out.extend(options)
        i += len(items)
    return out


def _split_marked_options(block: Block) -> list[Block]:
    """Kratki w tekście i „TAK NIE” na końcu linii - opcje są widoczne bez kontekstu."""
    if block.kind not in ("paragraph", "label", "heading"):
        return [block]
    text = block.text
    if _BOX.search(text):
        head, *options = _BOX.split(text)
        return _pieces(block, head, [o for o in options if o.strip()])
    match = _YES_NO.match(text)
    if match:
        return _pieces(block, match["prefix"], ["Tak", "Nie"])
    return [block]


def _pieces(block: Block, head: str, options: list[str]) -> list[Block]:
    out: list[Block] = []
    if head.strip():
        out.append(block.model_copy(update={"text": head.strip()}))
    for n, option in enumerate(options, 1):
        out.append(_option(block, option, n))
    return out or [block]


def _option(block: Block, text: str, n: int) -> Block:
    return block.model_copy(
        update={"id": f"{block.id}.{n}", "kind": "checkbox_option", "text": text.strip()}
    )


def _is_intro(block: Block) -> bool:
    if block.kind not in ("paragraph", "label", "heading") or has_fill(block):
        return False
    text = clean_text(block.text)
    return bool(text) and not _NOT_A_CHOICE.search(text) and not _ITEM_STOP.match(text)


def _list_items(blocks: list[Block], start: int) -> list[Block]:
    """Kolejne krótkie linie po wstępie; „inne ……” kończy listę jako ostatnia opcja."""
    items: list[Block] = []
    for block in blocks[start:]:
        if block.kind not in _OPTION_KINDS or len(items) >= MAX_OPTIONS:
            break
        text = clean_text(block.text)
        if (
            not text
            or len(text) > MAX_OPTION_CHARS
            or text.endswith(":")
            or _ITEM_STOP.match(text)
            or _NOT_A_CHOICE.search(text)
        ):
            break
        if has_fill(block):
            if len(text) <= MAX_OTHER_PREFIX_CHARS:
                items.append(block)
            break
        items.append(block)
    return items


def _as_options(intro: Block, items: list[Block]) -> list[Block] | None:
    """Opcje z pozycji listy, gdy wstęp i pozycje razem wyglądają na wybór; inaczej None."""
    if any(item.kind == "checkbox_option" for item in items):
        return None  # ekstrakcja już oznaczyła opcje
    texts = [clean_text(item.text) for item in items]
    # Opcja z miejscem do wpisania („inne ……”) zachowuje wykropkowanie, czyli `[POLE]`.
    pieces = [
        [_NUMBER_PREFIX.sub("", item.text, count=1)]
        if has_fill(item)
        else _split_inline_numbering(text)
        for item, text in zip(items, texts, strict=True)
    ]
    count = sum(len(p) for p in pieces)
    if count < MIN_OPTIONS:
        return None
    intro_text = clean_text(intro.text)
    colon = bool(_COLON_END.search(intro_text))
    numbered = all(_NUMBER_PREFIX.match(text) for text in texts)
    short_list = (
        count >= MIN_SHORT_OPTIONS
        and all(len(t) <= MAX_SHORT_OPTION_CHARS for t in texts)
        and not any(_FIELD_LABEL.search(t) for t in texts)
    )
    choice = (
        bool(_STRONG_CUE.search(intro_text))
        or (bool(_WEAK_CUE.search(intro_text)) and (colon or numbered))
        or (colon and short_list)
    )
    if not choice:
        return None
    out: list[Block] = []
    for item, parts in zip(items, pieces, strict=True):
        if len(parts) == 1:
            out.append(item.model_copy(update={"kind": "checkbox_option", "text": parts[0]}))
        else:
            out.extend(_option(item, part, n) for n, part in enumerate(parts, 1))
    return out


def _split_inline_numbering(text: str) -> list[str]:
    """„1. a 2. b 3. c” → [a, b, c], gdy numery idą po kolei; inaczej [tekst bez numeru]."""
    matches = list(_INLINE_NUMBER.finditer(text))
    numbers = [int(m.group(1)) for m in matches]
    if len(matches) >= 2 and numbers == list(range(numbers[0], numbers[0] + len(numbers))):
        bounds = [m.start() for m in matches[1:]] + [len(text)]
        parts = [text[m.end() : end].strip() for m, end in zip(matches, bounds, strict=True)]
        return [p for p in parts if p]
    return [_NUMBER_PREFIX.sub("", text, count=1) or text]
