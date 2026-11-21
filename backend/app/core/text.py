"""Pomocnicze funkcje tekstowe wspólne dla modeli i budowy formularza."""

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# NFKD nie rozkłada `ł`, więc mapujemy je ręcznie (spec §4: bez Unidecode).
_EXTRA = str.maketrans({"ł": "l", "Ł": "L"})


def to_tech_name(text: str) -> str:
    """snake_case ASCII z tekstu: `Numer PESEL` → `numer_pesel`, `Łódź` → `lodz`."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_EXTRA))
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALNUM.sub("_", ascii_text.lower()).strip("_")
