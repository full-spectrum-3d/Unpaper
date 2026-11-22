"""Schematy odpowiedzi do dokumentacji OpenAPI.

Endpointy zwracają zwykłe słowniki (`response_model=None`), więc te modele niczego nie
filtrują w czasie działania - opisują tylko kształt JSON-a w Swaggerze. Przy zmianie
kluczy w `pipeline/convert.py`, `pipeline/review.py` albo `api/v1/catalog.py` zaktualizuj
też odpowiedni model; testy w `tests/test_openapi.py` porównują przykłady z serwerem.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.models.dictionary import DictionaryItem, DictionaryProposal
from app.models.warning import ConversionWarning

Level = Literal["high", "medium", "low"]


class Issue(BaseModel):
    """Błąd reguły albo wykonana poprawka."""

    code: str = Field(description="Kod reguły, np. `R04_TECHNAME_UNIQUE`", examples=["R09_OPTIONS"])
    message: str = Field(description="Opis problemu po polsku")
    path: str | None = Field(
        default=None,
        description="Ścieżka JSON do miejsca, którego dotyczy, np. "
        "`tabs[0].questions[2].field.options`",
    )


class ValidationResult(BaseModel):
    """Wynik `POST /forms/validate`."""

    valid: bool = Field(description="`true`, gdy nie ma żadnego błędu (ostrzeżenia nie blokują)")
    errors: list[Issue] = Field(
        description="Naruszenia JSON Schema i reguł R01-R16; formularz z błędami nie "
        "zaimportuje się do Generatora"
    )
    warnings: list[ConversionWarning] = Field(
        description="Ostrzeżenia `Wnn_*`: formularz jest poprawny, ale warto go przejrzeć"
    )


# --- Katalogi ---


class PredefinedDictionary(BaseModel):
    name: str = Field(description="Nazwa słownika do pola `dictionaryName`")
    description: str
    status: Literal["PREDEFINED"]
    fieldTypes: list[str] = Field(description="Typy pól, które mogą używać słownika")
    multiLevelTree: bool = Field(description="Słownik wielopoziomowy (np. TERYT)")


class ProposedDictionary(BaseModel):
    name: str
    title: str
    description: str
    status: Literal["PROPOSED"] = Field(
        description="Słownik jeszcze nie istnieje w Generatorze; pole zachowuje opcje inline"
    )
    fieldTypes: list[str]
    itemStructure: list[str] = Field(description="Kolumny pozycji słownika")
    items: list[DictionaryItem]


class DictionaryCatalog(RootModel[list[PredefinedDictionary | ProposedDictionary]]):
    """Słowniki predefiniowane, potem proponowane."""


class InitialDataAttribute(BaseModel):
    attribute: str = Field(description="Nazwa atrybutu w źródle", examples=["firstName"])
    ref: str = Field(description="Wartość do `defaultValue` pola", examples=["PESEL.firstName"])
    label: str = Field(description="Etykieta pola po polsku", examples=["Imię"])
    fieldType: str = Field(description="Typ pola formularza", examples=["TEXT_FIELD"])
    editable: bool = Field(description="Czy użytkownik może zmienić wartość z rejestru")


class InitialDataSource(BaseModel):
    source: str = Field(examples=["PESEL"])
    name: str = Field(examples=["Rejestr PESEL"])
    attributes: list[InitialDataAttribute]


class InitialDataSources(RootModel[list[InitialDataSource]]):
    """Źródła danych inicjalnych (spec §8.5)."""


class TerytNode(BaseModel):
    name: str
    code: str | None = None
    children: list[TerytNode] | None = None


class TerytTree(BaseModel):
    asOf: str = Field(description="Data stanu rejestru TERYT")
    levels: list[str] = Field(description="Nazwy poziomów drzewa, od najwyższego")
    items: list[TerytNode]


# --- Raport konwersji ---


class SourceFileReport(BaseModel):
    name: str
    mime: str
    sizeBytes: int
    pages: int | None
    decrypted: bool = Field(description="Plik był zaszyfrowany i otwarto go podanym hasłem")


class ExtractionReport(BaseModel):
    method: str = Field(description="Sposób odczytu tekstu (warstwa tekstowa, OCR, OOXML…)")
    convertedToOpenXml: bool = Field(description="DOC/ODS przekonwertowane przez LibreOffice")
    ocrMeanConfidence: float | None
    blocks: int = Field(description="Liczba bloków tekstu znalezionych w dokumencie")


class LlmReport(BaseModel):
    model: str | None
    durationMs: int | None
    retries: int
    fallback: bool = Field(description="Model nie dał poprawnej odpowiedzi; użyto reguł")
    fallbackReason: str | None
    ruleBasedDraft: bool
    promptTokens: int | None
    outputTokens: int | None


class FormStats(BaseModel):
    tabs: int
    sections: int
    fields: int
    states: int = Field(description="Liczba warunków widoczności (JSONata)")


class Confidence(BaseModel):
    score: float = Field(ge=0, le=1, description="Ogólna pewność konwersji 0-1")
    level: Level
    fieldsTotal: int
    fieldsFromDocument: int
    toReview: int = Field(description="Liczba pozycji w `review`")


class SourceBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class FieldSource(BaseModel):
    """Miejsce w dokumencie, z którego pochodzi etykieta pola (współrzędne jako ułamki strony)."""

    model_config = ConfigDict(extra="allow")

    page: int
    blockId: str
    text: str
    box: SourceBox | None = None
    pageAspect: float | None = None


class FieldReview(BaseModel):
    model_config = ConfigDict(extra="allow")

    techName: str
    title: str
    tab: str
    section: str
    origin: Literal["document", "template"] = Field(
        description="`template` - sekcja predefiniowana, niezależna od dokumentu"
    )
    confidence: float
    level: Level
    reasons: list[dict[str, Any]]
    source: FieldSource | None = None


class ReviewItem(BaseModel):
    """Pozycja do przejrzenia: pole o niskiej pewności albo problem całego formularza."""

    model_config = ConfigDict(extra="allow")

    kind: Literal["field", "form"]
    level: Level
    title: str
    messages: list[str]
    techName: str | None = None
    tab: str | None = None
    code: str | None = None


class ConversionReport(BaseModel):
    sourceFile: SourceFileReport
    extraction: ExtractionReport
    llm: LlmReport
    stats: FormStats
    dictionaryProposals: list[DictionaryProposal]
    warnings: list[ConversionWarning]
    fixes: list[Issue] = Field(description="Poprawki wykonane automatycznie przez weryfikację")
    timings: dict[str, int] = Field(description="Czas etapów w ms, np. `extractMs`, `llmMs`")
    confidence: Confidence
    fields: list[FieldReview]
    review: list[ReviewItem]
    durationMs: int


class ConvertWithReport(BaseModel):
    """Odpowiedź `POST /forms/convert?report=true`."""

    form: dict[str, Any] = Field(description="Konfiguracja formularza w formacie importu (spec §7)")
    report: ConversionReport


class ConvertResponse(RootModel[ConvertWithReport | dict[str, Any]]):
    """Sam formularz (domyślnie) albo `{form, report}` przy `report=true`."""
