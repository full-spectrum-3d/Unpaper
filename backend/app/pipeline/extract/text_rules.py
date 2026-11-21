"""Reguły tekstowe wspólne dla wszystkich formatów (projekt ekstrakcji §4.4).

Rozpoznają glify checkboxów (także znaki Wingdings/Symbol z prywatnego obszaru Unicode,
którymi Word i PDF-y z Worda rysują kratki), wykropkowania i nagłówki.
"""

import re

from app.models.document import FILL_RUN

CHECKBOX_GLYPHS = frozenset(
    "☐□■▢◻❑❒☑☒"
    # Wingdings / Symbol w obszarze prywatnym: kratki, kółka, „ptaszki”.
    ""
)

HEADING_MAX_CHARS = 150
HEADING_SIZE_RATIO = 1.15
HEADING_UPPER_RATIO = 0.8
HEADING_MIN_UPPER_LETTERS = 6

_GLYPH_SPLIT = re.compile("[" + re.escape("".join(sorted(CHECKBOX_GLYPHS))) + "]")
_FILL_NOISE = re.compile(r"[\s.…_:()\[\]/-]+")
_HEADING_STYLE = re.compile(r"(?i)^(heading|nagłówek|title|tytuł)\b")
_FORMAT_MASK = re.compile(r"\w{1,4}([-./]\w{1,4})+")
"""Maska formatu, np. „DD-MM-RRRR” - to podpowiedź, nie nagłówek."""


def split_checkbox_options(text: str) -> list[str] | None:
    """Teksty opcji, gdy tekst zaczyna się glifem checkboxa; inaczej `None`.

    „☐ Tak ☐ Nie” → ["Tak", "Nie"]. Pusta opcja (sam glif) jest pomijana.
    """
    stripped = text.lstrip()
    if not stripped or stripped[0] not in CHECKBOX_GLYPHS:
        return None
    parts = (part.strip() for part in _GLYPH_SPLIT.split(stripped))
    return [part for part in parts if part]


def has_checkbox_glyph(text: str) -> bool:
    return any(ch in CHECKBOX_GLYPHS for ch in text)


def is_fill_only(text: str) -> bool:
    """Tekst to samo miejsce do wypełnienia: wykropkowanie, ewentualnie z nawiasem i `:`."""
    if not FILL_RUN.search(text):
        return False
    return not _FILL_NOISE.sub("", text)


def is_heading_style(style_name: str | None) -> bool:
    return bool(style_name) and bool(_HEADING_STYLE.match(style_name or ""))


def looks_like_heading(
    text: str, *, bold: bool, size: float | None, body_size: float | None, alone: bool
) -> bool:
    """Nagłówek po rozmiarze, pogrubieniu (cały segment, jedyny w linii) albo wersalikach."""
    text = text.strip()
    if not text or len(text) > HEADING_MAX_CHARS or FILL_RUN.search(text):
        return False
    if (
        has_checkbox_glyph(text)
        or text[0].islower()
        or text[0] in "(["
        or text.endswith(":")
        or _FORMAT_MASK.fullmatch(text.replace(" ", ""))
    ):
        return False
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    if size is not None and body_size and size >= body_size * HEADING_SIZE_RATIO:
        return True
    if bold and alone:
        return True
    upper = sum(1 for ch in letters if ch.isupper())
    return upper >= HEADING_MIN_UPPER_LETTERS and upper / len(letters) >= HEADING_UPPER_RATIO
