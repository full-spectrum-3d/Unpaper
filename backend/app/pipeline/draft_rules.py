"""Reguły bez LLM: oświadczenia z blankietu, pola dublujące dane wnioskodawcy i wyliczane.

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
        "mail", "i", "lub", "oraz", "wnioskodawcy", "wnioskodawca", "opcjonalnie", "pełna",
        "skrócona", "pierwsze", "drugie",
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
# Składowe adresu. Dublują sekcje predefiniowane tylko w sekcji o adresie lub danych
# wnioskodawcy (np. „Miejscowość” w „Adres zamieszkania”), a nie w „Adres nieruchomości”.
_ADDRESS_WORDS = frozenset(
    {
        "kraj", "województwo", "powiat", "gmina", "miejscowość", "miejscowości", "ulica", "ul",
        "domu", "lokalu", "budynku", "kod", "pocztowy", "poczta", "pocztowa", "adres", "nr",
        "numer", "i", "lub", "oraz", "/", "telefonu", "telefon", "e-mail", "email", "faks", "fax",
        "tel", "poczty", "elektronicznej", "skrzynki", "epuap", "kontaktowy", "kontaktowe",
    }
)  # fmt: skip
_APPLICANT_CONTEXT = re.compile(
    r"(?i)wnioskodawc|składając|podmiotu zobowiązanego|dane identyfikacyjne|dane kontaktowe"
    r"|dane do kontaktu|adres\w*\W+(\w+\W+){0,3}?(zamieszkania|siedziby|do korespondencji)"
    r"|korespondencyjn"
)
# ...chyba że sekcja dotyczy przedmiotu sprawy: „Dane identyfikacyjne nieruchomości”.
_SUBJECT_CONTEXT = re.compile(
    r"(?i)nieruchomoś|działk|budyn|lokal\w* (mieszk|użytk)|obiekt|pojazd|zwierz|\bps(a|ów|y)\b"
    r"|drog|teren|inwestycj|robót|świetlic|imprez|zgromadz"
)
_APPLICANT_WORD = re.compile(r"(?i)wnioskodawc")
# Podpis (także innej osoby: kandydata, rodzica) to w e-formularzu podpis elektroniczny.
_SIGNATURE_LABEL = re.compile(r"(?i)^\W*(czytelny\s+|własnoręczny\s+)?podpis\b")
# Numer pozycji przed oświadczeniem („35.”) w deklaracjach: to pole do zaznaczenia.
_POSITION_NUMBER = re.compile(r"^\s*\d{1,3}\.?\s*$")
# Warianty do skreślenia: „wynajęcie/użyczenie*”, „hodowanie/utrzymywanie*”.
_VARIANTS = re.compile(r"(?<![\w/])(\w{3,}(?:/\w{3,})+)\s?\*(?!\*)")
VARIANT_STEM = 4
# Sekcja o innej osobie niż wnioskodawca: tam imię, adres czy telefon to przedmiot sprawy.
_OTHER_PERSON = re.compile(
    r"(?i)\bosob(a|y|ie|ę|ą)\b|pełnomocni|właściciel|wykonawc|kierownik|inwestor|zmarł|dzieck|"
    r"dziec|małżon|rodzic|opiekun|kandydat|sportowc|zawodni|trener|podopieczn|uczestni|"
    r"najemc|dzierżawc|spadkobierc|świadk|członk|reprezentant|pracownik|ucz(eń|nia)"
)


# Wartości wyliczane: etykieta zaczyna się od słowa wyniku albo stawki („Stawka opłaty”,
# „Wysokość miesięcznej opłaty”, „Suma…”, „Razem”) albo odwołuje się do innych pozycji
# („Kwota z poz. 12”, „poz. 3 + poz. 4”, „pomniejszona o”). Sama „Wysokość opłaty”
# (bez okresu czy rodzaju) to zwykle kwota, którą wnioskodawca zapłacił i wpisuje.
_RATE_LABEL = re.compile(r"^stawk\w*\b")
_COMPUTED_LABEL = re.compile(
    r"^((wysokość|kwot[ay])\s+\w+\b.*?\bopłat\w*|sum[ay]|razem|łącznie|ogółem)\b"
    r"|\bz poz\.|\bpoz\.\s*\d+\w*\s*[+-]\s*(poz\.\s*)?\d|\bpomniejszon\w*\s+o\b"
)
_LEADING_POSITION = re.compile(r"^[\W\d]+")


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
            or (i >= 2 and _POSITION_NUMBER.match(blocks[i - 2].text))
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
    if _SIGNATURE_LABEL.match(label) or (
        words <= _SIGNATURE_WORDS
        and (
            "podpis" in words
            or ("data" in words and words & {"miejscowość", "złożenia", "sporządzenia"})
        )
    ):
        return "miejsce i data złożenia oraz podpis są w sekcjach systemowych"
    titles = list(context)
    # „Osoba wnioskodawca” to nadal wnioskodawca, a nie inna osoba.
    other_person = any(
        _OTHER_PERSON.search(title) and not _APPLICANT_WORD.search(title) for title in titles
    )
    if words <= _PERSONAL_WORDS and words & _PERSONAL_KEYS:
        if not words & {"wnioskodawcy", "wnioskodawca"} and other_person:
            return None
        return "dane wnioskodawcy są w sekcjach predefiniowanych"
    if words <= _ADDRESS_WORDS | _PERSONAL_WORDS and not other_person and _applicant_titled(titles):
        return "adres i dane kontaktowe wnioskodawcy są w sekcjach predefiniowanych"
    return None


def computed_field_reason(label: str, section_labels: list[str]) -> str | None:
    """Dlaczego pole to wartość wyliczana albo stawka z cennika, albo None.

    `section_labels` to etykiety pozostałych pól liczbowych sekcji. Pole usuwamy tylko
    wtedy, gdy obok jest pole liczbowe spoza tej reguły (dane wejściowe, np. „Liczba osób”):
    bez niego nie ma z czego wyliczyć, więc „Wysokość dochodu na osobę” zostaje.
    """
    kind = _computed_kind(label)
    if kind is None or not any(_computed_kind(other) is None for other in section_labels):
        return None
    if kind == "rate":
        return "stawka wynika z uchwały lub cennika, wnioskodawca jej nie wpisuje"
    return "wartość wylicza się z innych pól, wnioskodawca jej nie wpisuje"


def _computed_kind(label: str) -> str | None:
    text = _LEADING_POSITION.sub("", _norm(label))
    if _RATE_LABEL.match(text):
        return "rate"
    if _COMPUTED_LABEL.search(text):
        return "computed"
    return None


def _applicant_titled(titles: list[str]) -> bool:
    """Czy najbliższy tytuł (sekcja, potem strona) mówi o adresie lub danych wnioskodawcy."""
    for title in titles:
        if _SUBJECT_CONTEXT.search(title):
            return False
        if _APPLICANT_CONTEXT.search(title):
            return True
    return False


def is_statement(text: str) -> bool:
    """Czy tekst zaczyna się jak oświadczenie („Oświadczam, że…”, „2. Zobowiązuję się…”)."""
    return bool(_STATEMENT.match(_NUMBERING.sub("", clean_text(text))))


def variant_choices(doc: DocumentModel) -> list[list[str]]:
    """Warianty do skreślenia z dokumentu („wynajęcie/użyczenie*”), bez form jednego słowa.

    „charta/chartów*” to odmiana jednego wyrazu (wspólny rdzeń), a nie wybór.
    Te same warianty w innej formie („wynajem/użyczenie*”) zwracamy raz.
    """
    out: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for _, block in doc.iter_content_blocks():
        for match in _VARIANTS.finditer(block.text):
            variants = match.group(1).split("/")
            stems = tuple(v.casefold()[:VARIANT_STEM] for v in variants)
            if len(set(stems)) < len(stems) or stems in seen:
                continue
            if any(v.casefold() in _PERSONAL_WORDS for v in variants):
                continue
            seen.add(stems)
            out.append(variants)
    return out


def same_stem(a: str, b: str) -> bool:
    return a.casefold()[:VARIANT_STEM] == b.casefold()[:VARIANT_STEM]


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
