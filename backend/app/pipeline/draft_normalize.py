"""Normalizacja szkicu LLM (projekt LLM §5.4 pkt 5).

Poprawia błędy, które nie uzasadniają ponownej próby, i każdą poprawkę zgłasza
ostrzeżeniem. Oświadczenia bierze z dokumentu (`draft_rules`), a nie od modelu.
Wynik zawsze przechodzi ponownie walidację `FormDraft`.
"""

import json
import re
from difflib import SequenceMatcher
from functools import cache
from importlib.resources import files
from typing import Any

from app.models.document import FIELD_MARKER, DocumentModel
from app.models.draft import CHOICE_KINDS, FormDraft
from app.models.warning import ConversionWarning
from app.pipeline.draft_repair import iter_field_dicts, remove_empty_containers, repair_conditions
from app.pipeline.draft_rules import (
    applicant_field_reason,
    covered_by,
    is_statement,
    same_stem,
    statements_from_document,
    variant_choices,
)

STATEMENT_FIELD_COVERAGE = 0.8
# Pole innego typu niż `info` uznajemy za oświadczenie tylko przy dłuższej etykiecie:
# krótkie etykiety („Rasa psa”) przypadkowo pokrywają się z tekstem oświadczeń.
MIN_STATEMENT_LABEL_CHARS = 25
GENERIC_OPTIONS = frozenset({"tak", "nie", "inne"})
STATEMENT_LIKE_KINDS = frozenset({"single_choice", "multi_choice", "short_text", "long_text"})
VARIANT_PAGE_TITLE = "Przedmiot wniosku"
VARIANT_SECTION_TITLE = "Rodzaj sprawy"
VARIANT_LABEL_WORDS = frozenset({"rodzaj", "lub", "albo", "wybór", "wniosku", "sprawy"})
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
    _remove_example_fields(data, doc_text, warnings)
    _remove_duplicate_fields(data, warnings)
    _remove_unnamed_attachments(data, warnings)
    data["statements"] = statements_from_document(doc)
    _remove_statement_fields(data, warnings)
    _add_variant_choices(data, doc, warnings)
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


@cache
def _example_labels() -> frozenset[str]:
    """Etykiety pól z przykładu few-shot w prompcie (`example_reply.json`)."""
    path = files("app") / "resources" / "prompts" / "example_reply.json"
    example = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(
        _normalize(field["label"])
        for page in example["subject_pages"]
        for section in page["sections"]
        for field in section["fields"]
    )


def _remove_example_fields(
    data: dict[str, Any], doc_text: str, warnings: list[ConversionWarning]
) -> None:
    """Pola przepisane z przykładu w prompcie, których nie ma w dokumencie, usuwamy.

    Przy fragmencie z niewielką treścią (np. druga strona oświadczenia) model potrafi
    oddać pola przykładu („Gatunek”, „Obwód pnia…”). Pole o takiej etykiecie zostaje,
    gdy etykieta lub któraś z opcji występuje w dokumencie.
    """
    examples = _example_labels()

    def leaked(field: dict[str, Any]) -> bool:
        if _normalize(field["label"]) not in examples:
            return False
        if not matches_text(field["label"], doc_text, LABEL_MATCH_THRESHOLD):
            return True
        # Ogólna etykieta („Rodzaj”) jest w każdym blankiecie - rozstrzygają opcje przykładu.
        options = [o for o in field["options"] if o.casefold() not in GENERIC_OPTIONS]
        return bool(options) and not any(
            matches_text(o, doc_text, LABEL_MATCH_THRESHOLD) for o in options
        )

    for path, field in iter_field_dicts(data):
        if leaked(field):
            warnings.append(
                ConversionWarning(
                    code="W28_EXAMPLE_FIELD_REMOVED",
                    message=f"Usunięto pole „{field['label']}”: pochodzi z przykładu w prompcie, "
                    "a nie z blankietu.",
                    path=path,
                )
            )
    for page in data["subject_pages"]:
        for section in page["sections"]:
            section["fields"] = [f for f in section["fields"] if not leaked(f)]


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
    """Pole z treścią oświadczenia dubluje zgodę w sekcji zgód - usuwamy je.

    Model zapisuje oświadczenia jako pola `info`, ale też jako wybór Tak/Nie albo
    pojedynczy checkbox. Pole innego typu usuwamy, gdy ma długą etykietę, która
    zaczyna się jak oświadczenie albo pokrywa się z oświadczeniem z blankietu.
    """
    statements = " ".join(data["statements"])
    if not statements:
        return

    def is_statement_field(field: dict[str, Any]) -> bool:
        label: str = field["label"]
        covered = covered_by(label, statements) >= STATEMENT_FIELD_COVERAGE
        if field["kind"] == "info":
            return covered
        # Liczba, data czy plik to dane do wpisania, nawet gdy stoją w zdaniu oświadczenia
        # („Oświadczam, że średnia roczna liczba … wynosi ……”).
        if field["kind"] not in STATEMENT_LIKE_KINDS:
            return False
        return len(label) >= MIN_STATEMENT_LABEL_CHARS and is_statement(label)

    removed = {id(field) for _, field in iter_field_dicts(data) if is_statement_field(field)}
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


def _add_variant_choices(
    data: dict[str, Any], doc: DocumentModel, warnings: list[ConversionWarning]
) -> None:
    """Warianty do skreślenia („wynajęcie/użyczenie*”) jako pole wyboru, gdy model je pominął.

    Pole tekstowe z wariantami w etykiecie zamieniamy na wybór; gdy nie ma żadnego,
    dodajemy nowe na początku pierwszej sekcji.
    """
    fields = iter_field_dicts(data)
    for variants in variant_choices(doc):
        options = [v[:1].upper() + v[1:] for v in variants]

        def mentions(text: str, variants: list[str] = variants) -> bool:
            words = _WORD.findall(text)
            return all(any(same_stem(v, w) for w in words) for v in variants)

        if any(f["kind"] in CHOICE_KINDS and mentions(" ".join(f["options"])) for _, f in fields):
            continue
        label = " lub ".join([options[0], *variants[1:]])
        text_field = next(
            (
                (path, f)
                for path, f in fields
                if f["kind"] != "info" and mentions(f["label"]) and _only_variants(f, variants)
            ),
            None,
        )
        if text_field is not None:
            path, field = text_field
            field.update(kind="single_choice", options=options)
            message = f"Pole „{field['label']}” zamieniono na wybór: {', '.join(options)}."
        else:
            path = "subject_pages[0].sections[0].fields[0]"
            field = {
                "id": _next_id(data),
                "label": label,
                "kind": "single_choice",
                "required": True,
                "options": options,
                "visible_when": [],
            }
            if not data["subject_pages"]:
                data["subject_pages"].append({"title": VARIANT_PAGE_TITLE, "sections": []})
            page = data["subject_pages"][0]
            if not page["sections"]:
                page["sections"].append(
                    {"title": VARIANT_SECTION_TITLE, "repeating": False, "fields": []}
                )
            page["sections"][0]["fields"].insert(0, field)
            fields = iter_field_dicts(data)
            message = f"Dodano pole wyboru „{label}” z wariantów do skreślenia na blankiecie."
        warnings.append(ConversionWarning(code="W27_VARIANT_CHOICE", message=message, path=path))


def _only_variants(field: dict[str, Any], variants: list[str]) -> bool:
    """Etykieta to same warianty (+ słowo „rodzaj”), a nie np. „Cel wynajęcia/użyczenia”."""
    words = [w for w in _WORD.findall(field["label"]) if len(w) >= 3]
    rest = [w for w in words if not any(same_stem(v, w) for v in variants)]
    return all(w.casefold() in VARIANT_LABEL_WORDS for w in rest)


def _next_id(data: dict[str, Any]) -> str:
    numbers = [
        int(f["id"][1:]) for _, f in iter_field_dicts(data) if re.fullmatch(r"f\d+", f["id"])
    ]
    return f"f{max(numbers, default=0) + 1}"


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
