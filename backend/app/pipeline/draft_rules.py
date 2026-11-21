"""Reguły bez LLM: oświadczenia z blankietu i pola dublujące dane wnioskodawcy.

To, co da się ustalić z tekstu dokumentu deterministycznie, nie powinno zależeć
od modelu: model przepisujący oświadczenia zużywa najwięcej tokenów wyjścia
i parafrazuje je, a zakaz pól z danymi wnioskodawcy w prompcie bywa ignorowany.
"""

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from app.models.document import FIELD_MARKER, Block, DocumentModel

_FILL = re.compile(r"[.…_]{3,}")
_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"[\w-]+")
_NUMBERING = re.compile(r"^\s*(\d{1,2}[.)]|[a-z][.)/]|[-\u2013\u2022])\s*")

_STATEMENT = re.compile(
    r"(?i)\b(oświadczam|zobowiązuję się|przyjmuję do wiadomości|jestem świadom\w*)\b"
)
_DATA_CONSENT = re.compile(r"(?i)przetwarza\w*\W+(\w+\W+){0,8}?danych osobowych|\bRODO\b")
STATEMENT_KINDS = frozenset({"paragraph", "label", "checkbox_option"})
MAX_STATEMENT_ITEMS = 12
MAX_ITEM_CHARS = 400

# Etykiety pól z danymi wnioskodawcy: wszystkie słowa z tego słownika.
_PERSONAL_WORDS = frozenset(
    {
        "imię", "imiona", "nazwisko", "nazwa", "firmy", "adres", "zamieszkania",
        "korespondencji", "korespondencyjny", "do", "siedziby", "siedziba", "pesel", "nip",
        "regon", "numer", "nr", "telefonu", "telefon", "kontaktowy", "e-mail", "email",
        "mail", "i", "lub", "oraz", "wnioskodawcy", "wnioskodawca", "opcjonalnie",
    }
)  # fmt: skip
# ...i co najmniej jedno słowo, które jednoznacznie wskazuje dane osoby lub firmy.
_PERSONAL_KEYS = frozenset(
    {
        "imię", "imiona", "nazwisko", "pesel", "nip", "regon", "telefonu", "telefon",
        "e-mail", "email", "mail", "zamieszkania", "siedziby", "siedziba", "korespondencji",
        "korespondencyjny", "wnioskodawcy", "wnioskodawca",
    }
)  # fmt: skip
_SIGNATURE_WORDS = frozenset(
    {
        "miejscowość", "i", "data", "dnia", "podpis", "czytelny", "złożenia", "wniosku",
        "sporządzenia", "wnioskodawcy", "pieczątka", "pieczęć", "lub", "osoby", "upoważnionej",
    }
)  # fmt: skip
# Sekcja o innej osobie niż wnioskodawca: tam imię, adres czy telefon to przedmiot sprawy.
_OTHER_PERSON = re.compile(
    r"(?i)\bosob(a|y|ie|ę|ą)\b|pełnomocni|właściciel|wykonawc|kierownik|inwestor|zmarł|dzieck|"
    r"dziec|małżon|rodzic|opiekun|kandydat|sportowc|zawodni|trener|podopieczn|uczestni|"
    r"najemc|dzierżawc|spadkobierc|świadk|członk|reprezentant|pracownik|ucz(eń|nia)"
)


def clean_text(text: str) -> str:
    """Tekst bez wypełnień i znacznika pola, z pojedynczymi spacjami."""
    text = _FILL.sub(" ", text.replace(FIELD_MARKER, " "))
    return _WHITESPACE.sub(" ", text).strip()


def has_fill(block: Block) -> bool:
    return block.kind == "input_placeholder" or bool(_FILL.search(block.text))


def statements_from_document(doc: DocumentModel) -> list[str]:
    """Oświadczenia dosłownie z blankietu, bez zgód na przetwarzanie danych osobowych.

    Oświadczenie to blok z „oświadczam”, „zobowiązuję się” itp. Gdy kończy się
    dwukropkiem, kolejne bloki (do nagłówka albo miejsca na dane) to jego punkty.
    """
    blocks = [block for _, block in doc.iter_content_blocks()]
    statements: list[str] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        i += 1
        text = clean_text(block.text)
        if (
            block.kind not in STATEMENT_KINDS
            or has_fill(block)
            or not _STATEMENT.search(text)
            or _DATA_CONSENT.search(text)
        ):
            continue
        parts = [_NUMBERING.sub("", text)]
        if text.endswith(":"):
            while i < len(blocks) and len(parts) <= MAX_STATEMENT_ITEMS:
                item = blocks[i]
                item_text = clean_text(item.text)
                if (
                    item.kind not in STATEMENT_KINDS
                    or has_fill(item)
                    or not item_text
                    or len(item_text) > MAX_ITEM_CHARS
                ):
                    break
                parts.append(_NUMBERING.sub("", item_text))
                i += 1
        statement = " ".join(parts)
        if statement not in statements:
            statements.append(statement)
    return statements


def applicant_field_reason(label: str, context: Iterable[str]) -> str | None:
    """Dlaczego pole dubluje sekcje predefiniowane (dane wnioskodawcy, podpis), albo None.

    `context` to tytuły sekcji i strony: pole „Imię” w sekcji „Dane sportowca”
    dotyczy innej osoby i zostaje.
    """
    words = _words(label)
    if not words:
        return None
    if words <= _SIGNATURE_WORDS and (
        "podpis" in words
        or ("data" in words and words & {"miejscowość", "złożenia", "sporządzenia"})
    ):
        return "miejsce i data złożenia oraz podpis są w sekcjach systemowych"
    if not (words <= _PERSONAL_WORDS and words & _PERSONAL_KEYS):
        return None
    if not words & {"wnioskodawcy", "wnioskodawca"} and any(
        _OTHER_PERSON.search(title) for title in context
    ):
        return None
    return "dane wnioskodawcy są w sekcjach predefiniowanych"


def covered_by(needle: str, haystack: str) -> float:
    """Jaka część `needle` (po normalizacji) występuje w `haystack` - suma dopasowanych bloków."""
    n, h = _norm(needle), _norm(haystack)
    if not n:
        return 1.0
    matcher = SequenceMatcher(None, n, h, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(n)


def _norm(text: str) -> str:
    return _WHITESPACE.sub(" ", clean_text(text).casefold()).strip()


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(_norm(text).replace("/", " ")) if w not in {"-"}}
