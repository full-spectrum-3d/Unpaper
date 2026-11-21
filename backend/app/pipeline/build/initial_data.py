"""Dane inicjalne PESEL / PESEL_ADDRESS / MLPZ (spec §8.5)."""

import re

from app.models.form import ALLOWED_VALIDATORS, EXTERNAL_SYSTEM, FieldType
from app.models.warning import ConversionWarning
from app.pipeline.build.catalogs import load_initial_data_catalog
from app.pipeline.build.ir import FieldNode, PageNode, iter_fields
from app.pipeline.issues import IssueCode

IGNORED_TYPES = frozenset({FieldType.TEXT_BLOCK, FieldType.CONSENT_SECTION, FieldType.INFO_SECTION})

# Pola ze szkicu mają klucze `p<n>.s<n>.f<n>`; sekcje predefiniowane mają własne dane inicjalne.
_SUBJECT_KEY = re.compile(r"^p\d+(?:_\d+)?\.s\d+\.f\d+$")
# Etykieta lub tytuł sekcji wskazujący, że to nie dane osoby wnioskującej.
_OTHER_PERSON = re.compile(
    r"dziecka|dzieci\b|małżonk|pełnomocnik|innej\s+osoby|zmarłe|opiekun|przedstawiciel"
    r"|świadk|rodzic|współwłaściciel|reprezentant",
    re.IGNORECASE,
)

# Etykieta (cała, po normalizacji) na atrybut katalogu. Wolimy fałszywy brak niż fałszywe trafienie.
_EXACT_LABELS: dict[str, str] = {
    "data urodzenia": "PESEL.birthDate",
    "miejsce urodzenia": "PESEL.birthPlace",
    "imię matki": "PESEL.motherName",
    "imię ojca": "PESEL.fatherName",
    "nazwisko rodowe": "PESEL.familyName",
    "drugie imię": "PESEL.secondName",
    "stan cywilny": "PESEL.maritalStatus",
    "płeć": "PESEL.sex",
    "obywatelstwo": "PESEL.citizenship",
    "kraj urodzenia": "PESEL.birthCountry",
}
_ADDRESS_PARTS: dict[str, str] = {
    "województwo": "Voivodeship",
    "powiat": "District",
    "gmina": "Community",
    "miejscowość": "Place",
    "ulica": "Street",
    "numer domu": "HouseNumber",
    "numer lokalu": "ApartmentNumber",
    "kod pocztowy": "PostalCode",
}
_PART = "|".join(_ADDRESS_PARTS)
_KIND = r"(?:stały|stałego|tymczasowy|tymczasowego|czasowy|czasowego)"
# „[Stały|Tymczasowy] adres zameldowania: ulica” albo „Ulica zameldowania”. Samo „Ulica” nie.
_ADDRESS_LABELS = (
    re.compile(
        rf"^(?:(?P<k1>{_KIND})\s+)?adres\s+zameldowania(?:\s+(?P<k2>{_KIND}))?"
        rf"\s*[:\-–(]\s*(?P<part>{_PART})\)?$"  # noqa: RUF001
    ),
    re.compile(rf"^(?P<part>{_PART})\s+(?:adresu\s+)?zameldowania(?:\s+(?P<k1>{_KIND}))?$"),
)


def _normalized_label(label: str) -> str:
    return " ".join(label.lower().split()).rstrip(" :*")


def _catalog_ref(label: str) -> str | None:
    if ref := _EXACT_LABELS.get(label):
        return ref
    for rx in _ADDRESS_LABELS:
        if m := rx.match(label):
            kinds = [m.groupdict().get(k) or "" for k in ("k1", "k2")]
            temporary = any(k.startswith(("tymcz", "czas")) for k in kinds)
            prefix = "temporaryAddress" if temporary else "permanentAddress"
            return f"PESEL_ADDRESS.{prefix}{_ADDRESS_PARTS[m['part']]}"
    return None


def initial_data_ref(node: FieldNode, *, section_title: str, repeating: bool) -> str | None:
    """Atrybut katalogu dla pola przedmiotu sprawy albo `None`. Tylko jednoznaczne etykiety."""
    if (
        _SUBJECT_KEY.match(node.key) is None
        or repeating
        or node.initial_data is not None
        or node.dictionary_name is not None
        or node.type in IGNORED_TYPES
    ):
        return None
    label = _normalized_label(node.title)
    if _OTHER_PERSON.search(label) or _OTHER_PERSON.search(section_title):
        return None
    ref = _catalog_ref(label)
    attr = load_initial_data_catalog().get(ref) if ref else None
    if attr is None or node.type != attr.field_type:
        return None
    return attr.ref


def _infer_initial_data(pages: list[PageNode]) -> None:
    """Pola ze szkicu o jednoznacznej etykiecie dostają atrybut z rejestru (raz na formularz)."""
    used = {node.initial_data for _, _, node in iter_fields(pages) if node.initial_data}
    for _, section, node in iter_fields(pages):
        repeating = section.type is FieldType.REPEATING_SECTION
        ref = initial_data_ref(node, section_title=section.title, repeating=repeating)
        if ref is not None and ref not in used:
            node.initial_data = ref
            used.add(ref)


def apply_initial_data(pages: list[PageNode]) -> list[ConversionWarning]:
    _infer_initial_data(pages)
    catalog = load_initial_data_catalog()
    issues: list[ConversionWarning] = []
    for _, _, node in iter_fields(pages):
        if node.type in IGNORED_TYPES:
            continue
        ref = node.initial_data
        if ref is None:
            continue
        attr = catalog.get(ref)
        if attr is None or node.dictionary_name is not None:
            reason = "spoza katalogu" if attr is None else "pole ma słownik"
            node.initial_data = None
            issues.append(
                ConversionWarning(
                    code=IssueCode.W09_INITIAL_DATA_SKIPPED,
                    message=f"Pominięto dane inicjalne „{ref}” pola {node.tech_name} ({reason}).",
                    path=node.tech_name,
                )
            )
            continue
        if node.type != attr.field_type:
            node.type = attr.field_type
            node.options = []
            allowed = ALLOWED_VALIDATORS[node.type]
            node.validation = [v for v in node.validation if v in allowed]
        node.default_value = ref
        node.default_value_type = EXTERNAL_SYSTEM
        node.read_only = not attr.editable
    return issues
