# Budowa formularza i weryfikacja (pipeline [5] i [6]) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministyczna budowa `FormDefinition` (JSON importu COI) z `FormDraft`, czyli sekcje predefiniowane, mapowanie typów, walidatorów, słowników i danych inicjalnych, JSONata, układ, strony i `flow`. Do tego weryfikator JSON Schema + R01–R15 z autonaprawą i szkielet degradacji bez LLM.

**Architecture:**
- **IR.** Builder pracuje na wewnętrznej reprezentacji z `build/ir.py`: strony → sekcje → pola. Warunki widoczności to drzewo odwołujące się do kluczy węzłów.
- **Przebiegi.** Kolejno uzupełniają węzły: `techName`, słowniki, dane inicjalne, stany.
- **Serializacja.** `serialize.py` zamienia IR na słownik JSON w kształcie wzorców.
- **Weryfikacja.** `verify.py` działa na dowolnym słowniku JSON, także ręcznie poprawionym (`POST /forms/validate`), więc nie zależy od IR.

**Tech Stack:**
- Python 3.14, pytest.
- pydantic 2 (`FormDraft`).
- jsonschema (Draft 2020-12).
- jsonata-python 0.7: `jsonata.Jsonata(expr).evaluate(doc)`, `.assign(name, value)`, a błąd składni to `jsonata.JException`.

**Spec:** `docs/specyfikacja-techniczna.md` (§5.5, §5.6, §7, §8). Wzorce, czyli oczekiwany wynik:
- `wymagania/konfiguracja_form_wniosekOStwierdzenieNadplatyPodatku.json` (dalej **wzorzec N**);
- `wymagania/konfiguracja_form_wniosekOUstalenieNumeruPorzadkowegoNieruchomosci.json` (dalej **wzorzec P**).

Treści i reguły:
- `wymagania/HackNation - Standardy i dobre praktyki projektowania formularzy.md` (§2 „Budowa formularza”);
- `wymagania/Reguły techniczne konfiguracji formularzy i pól na formularzu - materiał do zadania obligatoryjnego.md`;
- transkrypcja zrzutów `docs/superpowers/specs/2026-11-21-form-build-screens.md`.

## Decyzje do tego planu (doprecyzowanie spec na podstawie wzorców)

- **Szablony sekcji predefiniowanych są wycięte ze wzorców 1:1.** Dotyczy to tytułów, `techName`, kolejności pól, słowników, danych inicjalnych, warunków i treści HTML. Odstępstwa są tylko tam, gdzie wzorce są ze sobą sprzeczne albo zawierają ewidentny błąd. Każde odstępstwo jest wymienione w Task 5 i w teście golden (Task 8):
  - `REQUIRED` zgodnie ze standardem (D4);
  - „Dane innej osoby” z polem `numer_pesel_inna_osoba` (standard);
  - „Dane podmiotu” z REGON i KRS (wzorzec P i standard);
  - tytuł „Opłata skarbowa za pełnomocnictwo” bez literówki;
  - adres innej osoby z `TERYT_4G_DOWODOWY`, `multiLevelTree` i `searchEnabled`, jak pozostałe adresy;
  - link RODO tylko z konfiguracji, bo wzorzec ma zepsuty `href`;
  - bez obrazków base64 w linkach.
- **Adres** ma kolejność pól i `y` jak we wzorcach:
  - `kraj` → `miejscowosc_zagranica` → `kod_pocztowy_zagranica` → `ulica_zagranica` → `wojewodztwo` → `kod_pocztowy` → `ulica` → `numer_budynku` → `numer_lokalu`;
  - sufiks kontekstu wchodzi przed `_zagranica`: `ulica_siedziba_zagranica`, `kraj_inna_osoba`;
  - pole TERYT ma `title` równy nazwie słownika (`TERYT_4G_DOWODOWY`), jak we wzorcach;
  - **nie ma** checkboxów „Brak …”: nie występują we wzorcach i jest to funkcja renderera. `read_only_when` zostaje dla pól ze szkicu.
- **Dane do kontaktu** zawierają tylko „Numer telefonu” i „Adres e-mail”, jak wzorce i standard. To korekta D9: nie ma osobnego numeru kierunkowego. Słownik `NUMERY_KIERUNKOWE` dostaje tylko pole z `semantic = PHONE_PREFIX`.
- **Tytuły stron:** „Dane”, potem strony przedmiotu z tytułami ze szkicu, potem „Kontakt i zgody”, potem „Strona końcowa” (FINISH). Stronę przedmiotu z więcej niż `max_sections_per_page` sekcjami dzielimy, a kolejne części mają tytuły `"{tytuł} (cd.)"`, `"{tytuł} (cd. 2)"` itd.
- **Układ jak we wzorcach:** `x=0`, `cols=3`, pole ma `rows=1`, sekcja `rows = liczba pól + 1`. `y` pola to indeks w sekcji, a `y` sekcji to skumulowana suma `rows` poprzednich sekcji na stronie. **`questionOrder = y`** dla pól i sekcji.
- **Opisy:**
  - `description` sekcji to zawsze dokument HTML, także pusty: `<html><head></head><body></body></html>`;
  - niepusty `description` pola to dokument HTML z akapitami `<p>`, a pusty to `""`;
  - `TEXT_BLOCK` i `CONSENT_SECTION` mają `title: ""`;
  - `consentSectionConfig` = `{"consents": [{"description", "required"}], "files": []}`.
- **`FormDefinition` to `dict[str, Any]`.** W `models/form.py` są tylko enumy i alias typu. `FormDraft` (`models/draft.py`) zawiera tyle, ile potrzebuje builder, a pod structured output LLM dopracujemy go później.
- **Testy w repo:** `backend/tests/unit/build/test_*.py` oraz golden `backend/tests/golden/test_reference_forms.py`.
- **Commity:** lead commituje po zaakceptowaniu każdego zadania, małym commitem w stylu Conventional Commits ze skilla `git-commit-messages`, bez linii `Co-Authored-By`. Implementerzy nie commitują.

## Global Constraints

- **Narzędzia.** Python `>=3.14` (adnotacje odroczone, bez `from __future__`). Kod w `backend/app/`, testy w `backend/tests/`. Polecenia uruchamiamy z `backend/`; muszą przechodzić:
  - `uv run pytest -q`;
  - `uv run ruff check app tests`, `uv run ruff format --check app tests`;
  - `uv run mypy app` (strict).
- **Styl.** Komentarze i docstringi po polsku, w stylu istniejących modułów (`app/pipeline/upload_validation/*.py`): docstring modułu z odwołaniem do paragrafu spec, bez rozwlekłych komentarzy. Testy po angielsku w nazwach funkcji, asercje na polskich danych.
- **Zależności.** Żadnych nowych (`jsonschema`, `jsonata-python` i `pydantic` już są).
- **Znaki typograficzne.** Treści po polsku z polskimi znakami. RUF001/RUF003 na typograficzne znaki w stringach z treścią wyciszamy `# noqa: RUF001` tylko w danej linii. Treści długie trzymamy w JSON-ach szablonów, a nie w kodzie.
- **`techName`.** snake_case ASCII `[a-z0-9_]`, maksymalnie 60 znaków. Polskie znaki transliterujemy: `ą→a, ć→c, ę→e, ł→l, ń→n, ó→o, ś→s, ź→z, ż→z`. Slug `Adres e-mail` → `adres_e_mail`, `Podatek, którego dotyczy nadpłata` → `podatek_ktorego_dotyczy_nadplata` (jak we wzorcu).
- **HTML.**
  - Linki zewnętrzne mają `rel="noopener noreferrer" target="_blank" aria-label="Link otwiera się w nowej karcie"`.
  - Tekst ze szkicu (pochodzi z LLM i dokumentu) **zawsze** przechodzi przez `html.escape` przed wstawieniem do HTML.
  - Treści szablonów są zaufane.
- **Klucze `field`.** Każdy `field` w wyniku ma klucze bazowe `id, type, techName, title, description, options, validation, readOnly, repeatingSectionGrid, states, questionOrder, tooltipMessage`, w tej kolejności. Klucze opcjonalne (`defaultValue, defaultValueType, dictionaryName, multiLevelTree, searchEnabled, consentSectionConfig, selectAllEnabled`) dopisujemy tylko wtedy, gdy mają wartość.
- **Walidatory:** `REQUIRED, EMAIL, PESEL, NIP, REGON, ZIP_CODE, EPUAP, ADE, SERIAL_NUMBER_ID_CARD`.
  - `TEXT_FIELD` przyjmuje wszystkie.
  - `TEXTAREA, NUMBER, SELECT, RADIO, CHECKBOX, DATEPICKER, FILE_UPLOADER` przyjmują tylko `REQUIRED`.
  - `TEXT_BLOCK, INFO_SECTION, CONSENT_SECTION, SECTION, REPEATING_SECTION` nie przyjmują żadnego.

## Review Focus

1. **Cudzysłów lub apostrof w wartości opcji albo tytule strony** (`Wniosek o „zwrot”`, `Kod 'A'`) nie może psuć JSONaty. Zapytanie się kompiluje i daje `true` tylko dla właściwej wartości. Test `test_quotes_in_values_and_titles` w Task 4.
2. **`visibleWhen` ze szkicu wskazuje etykietę, której nie ma** (halucynacja LLM) albo pole sekcji powtarzającej spoza tej sekcji. Wtedy budujemy bez stanu i z ostrzeżeniem `W03_CONDITION_UNRESOLVED`, bez wyjątku. Test `test_unresolved_condition_is_dropped_with_warning` w Task 7.
3. **Dwa pola o tej samej etykiecie** („Ulica” w adresie i na stronie przedmiotu) dostają różne `techName` (`ulica`, `ulica_2`), a warunek wskazuje właściwe pole: najpierw z tej samej sekcji, potem z tej samej strony, potem pierwsze w formularzu. Test `test_duplicate_labels_resolve_nearest` w Task 7.
4. **Ręcznie edytowany JSON z brakami** (brak `states` jak we wzorcu P, `validation: {}` jak we wzorcu P, zduplikowane `id`, pole poza sekcją, pusta strona, brak `flow`) przechodzi przez `verify_form(autofix=True)` bez wyjątku i wynik jest `valid`. Bez autonaprawy dostajemy listę błędów z kodami. Testy `test_broken_manual_json` i `test_reference_samples_are_repairable` w Task 6.
5. **Szkic z pustym `subjectPages` i samym `SELF`** daje poprawny formularz z 3 stronami („Dane”, „Kontakt i zgody”, FINISH), bez sekcji „Podmiot wniosku”. Test `test_minimal_draft` w Task 7.

---

### Task 1: Fundamenty: modele, IR, issues, HTML, katalogi, schemat

**Files:**
- Modify: `backend/app/models/form.py`, `backend/app/models/draft.py` (dziś zawierają same docstringi)
- Create: `backend/app/pipeline/issues.py`, `backend/app/pipeline/build/ir.py`, `backend/app/pipeline/build/html.py`, `backend/app/pipeline/build/catalogs.py`
- Modify: `backend/app/resources/dictionaries.json`, `backend/app/resources/initial_data.json`
- Create: `backend/app/resources/schema/importowanyPlikJsonSchemat.json` (usuń `.gitkeep` z tego katalogu)
- Create: `backend/tests/unit/build/__init__.py`, `backend/tests/unit/build/test_foundations.py`

**Interfaces:**
- Produces (`app/models/form.py`):
  - `class FieldType(StrEnum)`: `SECTION, REPEATING_SECTION, TEXT_FIELD, TEXTAREA, NUMBER, DATEPICKER, SELECT, RADIO, CHECKBOX, FILE_UPLOADER, TEXT_BLOCK, CONSENT_SECTION, INFO_SECTION`.
  - Zbiory typów:
    - `SECTION_TYPES: frozenset[FieldType]` = {SECTION, REPEATING_SECTION};
    - `INPUT_TYPES` = wszystkie typy poza sekcjami, `TEXT_BLOCK` i `INFO_SECTION`;
    - `CHOICE_TYPES` = {SELECT, RADIO, CHECKBOX}.
  - `class Validator(StrEnum)` (9 wartości) i `ALLOWED_VALIDATORS: dict[FieldType, frozenset[Validator]]` według Global Constraints.
  - `class TabType(StrEnum)`: `MAIN, FINISH`. `class StateType(StrEnum)`: `SHOW, READ_ONLY`. `EXTERNAL_SYSTEM = "EXTERNAL_SYSTEM"`.
  - `BASE_FIELD_KEYS: tuple[str, ...]` (12 kluczy w kolejności z Global Constraints), `EMPTY_HTML = "<html><head></head><body></body></html>"`, `type FormDefinition = dict[str, Any]`.
- Produces (`app/models/draft.py`, pydantic z `ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")`, więc JSON ma camelCase):
  - Enumy (StrEnum):
    - `ApplicantKind`: `SELF, OTHER_PERSON, LEGAL_ENTITY`;
    - `AddressKind`: `ZAMIESZKANIA, ZAMELDOWANIA, KORESPONDENCYJNY`;
    - `AuthorityKind`: `URZAD, ORGAN`;
    - `FieldKind`: `single_choice, multi_choice, short_text, long_text, number, date, file, info`;
    - `Semantic`: `PESEL, NIP, REGON, KRS, ZIP_CODE, EMAIL, PHONE, PHONE_PREFIX, EPUAP, ADE, ID_CARD, BANK_ACCOUNT, COUNTRY, VOIVODESHIP, DISTRICT, COMMUNITY, PLACE, FIRST_NAME, SECOND_NAME, LAST_NAME, FAMILY_NAME, BIRTH_DATE, BIRTH_PLACE, BIRTH_COUNTRY, CITIZENSHIP, SEX, MARITAL_STATUS, FATHER_NAME, FATHER_SURNAME, MOTHER_NAME, MOTHER_SURNAME`.
  - `DraftCondition(field: str, op: Literal["equals","not_equals","in"], value: str | None = None, values: list[str] = [])`. Walidator modelu: `in` wymaga niepustego `values`, pozostałe wymagają `value`.
  - `DraftField(label: str, kind: FieldKind, required: bool = False, options: list[str] = [], semantic: Semantic | None = None, about_applicant: bool = False, dictionary_candidate: str | None = None, description: str | None = None, tooltip: str | None = None, visible_when: DraftCondition | None = None, read_only_when: DraftCondition | None = None)`.
  - `DraftSection(title: str, repeating: bool = False, description: str | None = None, fields: list[DraftField], visible_when: DraftCondition | None = None)`, `DraftPage(title: str, sections: list[DraftSection])`, `Authority(kind: AuthorityKind = URZAD, name: str = "")`.
  - `FormDraft(title: str, authority: Authority = Authority(), applicant_kinds: list[ApplicantKind] = [SELF, OTHER_PERSON], addresses: list[AddressKind] = [ZAMIESZKANIA], subject_pages: list[DraftPage] = [], attachments: list[str] = [], statements: list[str] = [], summary_info: str | None = None)`.
- Produces (`app/pipeline/issues.py`):
  - `@dataclass(frozen=True, slots=True) class Issue(code: str, message: str, path: str | None = None)` z `to_dict() -> dict[str, str]` (bez `path`, gdy jest `None`).
  - `class IssueCode(StrEnum)` z kodami:
    - `SCHEMA`;
    - reguły: `R01_TITLE, R02_TABS, R03_EMPTY_PAGE, R03_FIELD_OUTSIDE_SECTION, R04_NESTED_SECTION, R05_FINISH_INPUT, R06_REQUIREDNESS, R07_FLOW, R08_DICTIONARY, R09_OPTIONS, R10_INITIAL_DATA, R11_STATE, R12_DUPLICATE_TECH_NAME, R12_DUPLICATE_ID, R13_CONSENT, R14_INFO_SECTION, R15_VALIDATOR`;
    - ostrzeżenia: `W01_LLM_FALLBACK, W02_LABEL_TOO_LONG, W03_CONDITION_UNRESOLVED, W04_DUPLICATE_PREDEFINED_FIELD, W05_TITLE_PREFIX, W06_STATE_REMOVED, W07_CHOICE_OPTIONS, W08_TITLE_TRUNCATED, W09_INITIAL_DATA_SKIPPED, W10_ATTACHMENT_DUPLICATE`.
- Produces (`app/pipeline/build/ir.py`, dataclasses):
  - Warunki (frozen): `Eq(ref: str, value: str)`, `Not(cond: Condition)`, `AllOf(items: tuple[Condition, ...])`, `AnyOf(items: tuple[Condition, ...])`, `type Condition = Eq | Not | AllOf | AnyOf`. `ref` to `key` węzła pola.
  - `Consent(description_html: str, required: bool)`, gdzie `description_html` to fragment `<body>`.
  - `FieldNode` z polami:
    - wymagane: `key: str, type: FieldType, title: str, tech_name: str`;
    - treść: `description_html: str = ""` (fragment `<body>`, pusty = brak opisu), `tooltip: str = ""`, `options: list[str]`, `validation: list[Validator]`, `read_only: bool = False`;
    - słownik i wartość domyślna: `dictionary_name: str | None`, `search_enabled: bool | None`, `multi_level_tree: bool | None`, `default_value: str | list[str] | None`, `default_value_type: str | None`;
    - dane inicjalne i zgody: `initial_data: str | None` (np. `"MLPZ.name"`), `consents: list[Consent]`, `select_all_enabled: bool | None`;
    - ze szkicu: `semantic: Semantic | None`, `about_applicant: bool = False`, `dictionary_candidate: str | None`;
    - warunki: `show_when: Condition | None`, `read_only_when: Condition | None`, `pending_show_when: DraftCondition | None`, `pending_read_only_when: DraftCondition | None`.
  - `SectionNode(key: str, type: FieldType, title: str, tech_name: str, description_html: str = "", fields: list[FieldNode], show_when: Condition | None = None, pending_show_when: DraftCondition | None = None)`.
  - `PageNode(key: str, title: str, type: TabType, sections: list[SectionNode])`.
  - `iter_fields(pages: list[PageNode]) -> Iterator[tuple[PageNode, SectionNode, FieldNode]]`.
- Produces (`app/pipeline/build/html.py`):
  - `html_document(body: str) -> str` daje `<html><head></head><body>{body}</body></html>`;
  - `paragraphs(*texts: str) -> str` escapuje i owija w `<p>…</p>` każdy niepusty tekst;
  - `external_link(href: str, text: str) -> str` escapuje oba argumenty i dodaje atrybuty z Global Constraints.
- Produces (`app/pipeline/build/catalogs.py`):
  - `@dataclass(frozen=True) DictionaryEntry(name: str, description: str, field_types: tuple[FieldType, ...], multi_level_tree: bool, semantics: frozenset[Semantic])`.
  - `@dataclass(frozen=True) InitialDataAttribute(source: str, attribute: str, label: str, field_type: FieldType, editable: bool)` z property `ref -> str` (np. `"MLPZ.name"`).
  - `load_dictionary_catalog() -> dict[str, DictionaryEntry]` i `load_initial_data_catalog() -> dict[str, InitialDataAttribute]` (klucz to `ref`), oba z `@cache`. Czytają zasoby przez `importlib.resources.files("app.resources")`.
  - `load_form_schema() -> dict[str, Any]` (`@cache`).

- [ ] **Step 1: Napisz testy w `tests/unit/build/test_foundations.py`:**
  - `test_draft_parses_camel_case`: `FormDraft.model_validate({"title": "Wniosek o X", "applicantKinds": ["SELF"], "subjectPages": [{"title": "P", "sections": [{"title": "S", "fields": [{"label": "A", "kind": "short_text", "aboutApplicant": True}]}]}]})` ma `.subject_pages[0].sections[0].fields[0].about_applicant is True`.
  - `test_condition_in_requires_values`: `DraftCondition(field="a", op="in")` rzuca `ValidationError`.
  - `test_allowed_validators`:
    - `ALLOWED_VALIDATORS[FieldType.NUMBER] == {Validator.REQUIRED}`;
    - `ALLOWED_VALIDATORS[FieldType.TEXT_BLOCK] == frozenset()`;
    - `ALLOWED_VALIDATORS[FieldType.TEXT_FIELD]` ma 9 elementów.
  - `test_html_helpers`:
    - `paragraphs("a<b", "") == "<p>a&lt;b</p>"`;
    - `'rel="noopener noreferrer"' in external_link("https://x.pl", "x")`;
    - `html_document("") == EMPTY_HTML`.
  - `test_initial_data_catalog`:
    - `["PESEL.birthDate"].field_type is FieldType.DATEPICKER`;
    - liczba refów z prefiksem `PESEL.` to 16, `PESEL_ADDRESS.` 18, `MLPZ.` 17;
    - `["MLPZ.email"].editable is True`, `["MLPZ.name"].editable is False`.
  - `test_dictionary_catalog`: `["TERYT_4G_DOWODOWY"].multi_level_tree is True`, a `"Kraje"` ma `Semantic.COUNTRY`.
  - `test_schema_accepts_reference_samples`: `Draft202012Validator(load_form_schema())` nie zgłasza błędów dla obu wzorców z `wymagania/` (ścieżka liczona od `Path(__file__).parents[4] / "wymagania"`). Odrzuca też pole z `defaultValue: 5` zagnieżdżone w `repeatingSectionGrid`.
- [ ] **Step 2: Uruchom** `uv run pytest tests/unit/build/test_foundations.py -q`. Oczekiwane: ImportError.
- [ ] **Step 3: Zaimplementuj** pliki z Interfaces. Zasoby:
  - `initial_data.json`: lista obiektów `{"source", "attribute", "label", "fieldType", "editable"}` przepisana 1:1 z `wymagania/Dane inicjalne - materialy dodatkowe do zadania rozszerzającego.md` (16 + 18 + 17 pozycji).
    - Typ: „Pole tekstowe” → `TEXT_FIELD`, „Datepicker” → `DATEPICKER`, pusty → `TEXT_FIELD`.
    - `editable: true` mają tylko `MLPZ.country, voivodeship, district, community, place, postCode, street, building, apartment, phoneNumber, email` (D10, wzorce: adres i kontakt z MLPZ bez `readOnly`).
  - `dictionaries.json`: lista `{"name", "description", "fieldTypes", "multiLevelTree", "semantics"}`:
    - `Kraje` (SELECT; `COUNTRY, BIRTH_COUNTRY, CITIZENSHIP`);
    - `TERYT_4G_DOWODOWY` (SELECT, `multiLevelTree: true`, bez semantyk);
    - `TERYT_DOWODOWY` (SELECT, `multiLevelTree: true`, bez semantyk);
    - `Województwo` (VOIVODESHIP), `Powiat` (DISTRICT), `Gmina` (COMMUNITY), `Miejscowość` (PLACE);
    - `NUMERY_KIERUNKOWE` (PHONE_PREFIX).
    Wszystkie z `fieldTypes: ["SELECT"]`, zgodnie z dokumentem „Słowniki”.
  - Schemat powstaje z `wymagania/importowanyPlikJsonSchemat.json` z poprawkami:
    - przebudowa na `$defs` `question` i `field` z rekurencją `repeatingSectionGrid.items → {"$ref": "#/$defs/question"}`;
    - zmiana nazwy `repetingSectionGrid` na `repeatingSectionGrid` (D1);
    - `defaultValue`: `{"type": ["string","array"], "items": {"type": "string"}}` (D5);
    - `validation`: `{"type": ["array","object"]}`, bo wzorzec P ma `{}`, a naprawia to dopiero verify;
    - `additionalProperties` niezdefiniowane (D6).
- [ ] **Step 4: Uruchom** test i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 2: `build/fields.py`: techName, typy, walidatory, warunki ze szkicu

**Files:**
- Modify: `backend/app/pipeline/build/fields.py`
- Test: `backend/tests/unit/build/test_fields.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `slugify(text: str, *, max_length: int = 60) -> str`:
    - transliteracja z Global Constraints, dla reszty znaków NFKD z odrzuceniem znaków łączących;
    - lowercase;
    - każdy ciąg znaków spoza `[a-z0-9]` → `_`, potem obcięcie `_` z brzegów;
    - pusty wynik → `"pole"`;
    - przy obcinaniu do `max_length` tniemy na ostatnim `_`, jeśli jest w drugiej połowie.
  - `normalize_title(raw: str) -> tuple[str, list[Issue]]`:
    - zwija białe znaki;
    - powyżej 255 znaków ucina i daje `W08_TITLE_TRUNCATED`;
    - brak prefiksu „Wniosek”, „Zgłoszenie”, „Deklaracja” ani „Oświadczenie” daje `W05_TITLE_PREFIX`;
    - pusty tytuł → `"Wniosek"` z `W05`.
  - `map_draft_field(field: DraftField, *, key: str) -> tuple[FieldNode, list[Issue]]`, według spec §8.3:
    - `short_text` → TEXT_FIELD, `long_text` → TEXTAREA, `number` → NUMBER, `date` → DATEPICKER, `file` → FILE_UPLOADER;
    - `single_choice`:
      - do 5 opcji → RADIO, powyżej 5 → SELECT;
      - `search_enabled=True` przy ponad 15 opcjach;
      - 1 opcja → CHECKBOX z `W07_CHOICE_OPTIONS`;
      - 0 opcji → TEXT_FIELD z `W07`;
    - `multi_choice` → CHECKBOX, a z 0 opcji → TEXT_FIELD z `W07`;
    - `info` → TEXT_BLOCK z `title=""`, `description_html = paragraphs(label, description or "")`, bez walidacji;
    - pozostałe typy: `description_html = paragraphs(description)`, gdy `description` jest podany; `tooltip = tooltip or ""`;
    - walidatory:
      - `REQUIRED`, gdy `required` i typ go dopuszcza;
      - z `semantic`: `PESEL, NIP, REGON, ZIP_CODE, EMAIL, EPUAP, ADE` i `ID_CARD → SERIAL_NUMBER_ID_CARD`;
      - przy `semantic is None` z etykiety, regexy bez rozróżniania wielkości liter: `\bpesel\b`, `\bnip\b`, `\bregon\b`, `kod\w*\s+pocztow`, `e-?mail|poczty\s+elektronicznej`, `\bepuap\b`, `e-?doręcze`, `seri\w*\s+i\s+numer\w*\s+dowodu`;
      - dodatkowe walidatory tylko dla TEXT_FIELD;
    - etykieta dłuższa niż 80 znaków → `W02_LABEL_TOO_LONG`;
    - przepisuje `semantic`, `about_applicant`, `dictionary_candidate`, `pending_show_when` (z `visible_when`) i `pending_read_only_when`;
    - `tech_name = slugify(label)`.
  - `convert_condition(cond: DraftCondition, resolve: Callable[[str], FieldNode | None]) -> Condition | None`: `equals` → `Eq`, `not_equals` → `Not(Eq)`, `in` → `AnyOf(Eq…)` (przy jednym elemencie samo `Eq`). Gdy `resolve` zwraca `None`, wynik to `None`.
  - `assign_unique_tech_names(pages: list[PageNode]) -> None`: kolejność to strony → sekcja → jej pola. Pierwsze wystąpienie zostaje, kolejne dostają `_2`, `_3`. Sekcje i pola mają wspólną przestrzeń nazw.

- [ ] **Step 1: Napisz testy w `tests/unit/build/test_fields.py`:**
  - `test_slugify_matches_reference_tech_names` (parametryzowany):
    - „Numer PESEL” → `numer_pesel`;
    - „Adres e-mail” → `adres_e_mail`;
    - „Podatek, którego dotyczy nadpłata” → `podatek_ktorego_dotyczy_nadplata`;
    - „Wybierz, co mamy zrobić z nadpłatą” → `wybierz_co_mamy_zrobic_z_nadplata`;
    - „Urząd, do którego jest składany wniosek” → `urzad_do_ktorego_jest_skladany_wniosek`;
    - „Źródło łąki – ŻÓŁW” → `zrodlo_laki_zolw`;
    - „!!!” → `pole`.
  - `test_slugify_max_length`: `len(slugify("ab " * 50)) <= 60` i wynik nie kończy się `_`.
  - `test_normalize_title`: „  Karta   ” daje `"Karta"` i W05, a `"Wniosek " + "x"*300` daje 255 znaków i W08.
  - `test_choice_mapping`:
    - 3 opcje → RADIO;
    - 6 opcji → SELECT z `search_enabled is None`;
    - 16 opcji → SELECT z `search_enabled is True`;
    - 1 opcja → CHECKBOX z W07.
  - `test_validators`:
    - „Kod pocztowy” z `required` → `[REQUIRED, ZIP_CODE]`;
    - `kind=number`, `semantic=PESEL`, `required` → `[REQUIRED]`;
    - „Adres e-mail” bez `required` → `[EMAIL]`.
  - `test_info_field_is_text_block`: `type is TEXT_BLOCK`, `title == ""`, `description_html` zaczyna się od `<p>`, `validation == []`.
  - `test_label_is_escaped`: `description="<script>"` daje `"&lt;script&gt;"` w `description_html`.
  - `test_convert_condition`: `in` z dwiema wartościami → `AnyOf`, `not_equals` → `Not(Eq)`, a nieznana etykieta → `None`.
  - `test_assign_unique_tech_names`: dwa pola „Ulica” dostają `ulica` i `ulica_2`.
- [ ] **Step 2: Uruchom.** Oczekiwane: FAIL.
- [ ] **Step 3: Zaimplementuj.**
- [ ] **Step 4: Uruchom** testy i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 3: `build/dictionaries.py` i `build/initial_data.py`

**Files:**
- Modify: `backend/app/pipeline/build/dictionaries.py`, `backend/app/pipeline/build/initial_data.py`
- Test: `backend/tests/unit/build/test_catalog_passes.py`

**Interfaces:**
- Consumes: Task 1, `slugify` z Task 2 (implementuj przeciw sygnaturze, jeśli jeszcze go nie ma).
- Produces (`dictionaries.py`):
  - `@dataclass DictionaryProposal(name: str, items: list[str], used_by: list[str])` z `to_dict() -> dict[str, Any]`. Kształt wyniku:
    - `"name"`, `"status": "PROPOSED"`;
    - `"structure": ["code","name","techName","validFrom","validTo"]`;
    - `"items": [{"code": slugify(i).upper(), "name": i, "techName": slugify(i)}]`;
    - `"usedBy"`.
  - `apply_dictionaries(pages: list[PageNode]) -> list[DictionaryProposal]`:
    - Pole bez `dictionary_name`, którego `semantic` obsługuje słownik z katalogu, dostaje:
      - `dictionary_name`;
      - typ `field_types[0]`, a walidację przefiltrowaną przez `ALLOWED_VALIDATORS`;
      - `options=[]`, `search_enabled=True`;
      - `multi_level_tree=True` tylko dla słowników wielopoziomowych.
    - Pole z `dictionary_candidate` będącym nazwą z katalogu traktujemy tak samo.
    - Pole wyboru (`CHOICE_TYPES`) z kandydatem spoza katalogu, z co najmniej 2 opcjami i nazwą pasującą do `^[A-Z][A-Z0-9_]{2,63}$`, zostaje z opcjami inline i dodaje propozycję. Propozycje o tej samej nazwie łączymy: suma `used_by`, `items` z pierwszej.
    - Pass wywołujemy po `assign_unique_tech_names`.
- Produces (`initial_data.py`):
  - `APPLICANT_ATTRIBUTES: dict[Semantic, str]`:
    - `SECOND_NAME→"PESEL.secondName"`, `FAMILY_NAME→"PESEL.familyName"`;
    - `BIRTH_DATE→"PESEL.birthDate"`, `BIRTH_PLACE→"PESEL.birthPlace"`, `BIRTH_COUNTRY→"PESEL.birthCountry"`;
    - `CITIZENSHIP→"PESEL.citizenship"`, `SEX→"PESEL.sex"`, `MARITAL_STATUS→"PESEL.maritalStatus"`;
    - `FATHER_NAME→"PESEL.fatherName"`, `FATHER_SURNAME→"PESEL.fatherSurname"`, `MOTHER_NAME→"PESEL.motherName"`, `MOTHER_SURNAME→"PESEL.motherSurname"`.
  - `PREDEFINED_APPLICANT_SEMANTICS: frozenset[Semantic]` = {FIRST_NAME, LAST_NAME, PESEL, PHONE, EMAIL, ZIP_CODE}. Te pola z `about_applicant` usuwa builder (Task 7), bo są już w sekcjach predefiniowanych.
  - `apply_initial_data(pages: list[PageNode]) -> list[Issue]`, w trzech krokach:
    1. **Przypisanie:** pole z `about_applicant`, `semantic` w `APPLICANT_ATTRIBUTES`, bez `initial_data` i bez `dictionary_name` dostaje ref z mapy.
    2. **Weryfikacja każdego `initial_data`:**
       - ref spoza katalogu → zdjęcie `initial_data` i `W09_INITIAL_DATA_SKIPPED`;
       - pole z `dictionary_name` → zdjęcie i `W09`;
       - typ inny niż typ atrybutu → typ atrybutu, `options=[]` i walidacja przefiltrowana przez `ALLOWED_VALIDATORS`.
    3. **Ustawienie:** `default_value=ref`, `default_value_type=EXTERNAL_SYSTEM`, `read_only = not attr.editable`.

- [ ] **Step 1: Napisz testy w `tests/unit/build/test_catalog_passes.py`:**
  - `test_country_semantic_gets_dictionary`: `dictionary_name == "Kraje"`, `options == []`, `search_enabled is True`, `multi_level_tree is None`.
  - `test_dictionary_proposal`: RADIO z 3 opcjami i `dictionary_candidate="RODZAJE_PODATKOW"` zostaje RADIO z opcjami. `to_dict()` ma `status == "PROPOSED"`, `usedBy == [tech_name]` oraz `items[0] == {"code": …, "name": …, "techName": …}`.
  - `test_proposals_merge_by_name`: dwa pola dają jedną propozycję z dwoma `usedBy`.
  - `test_invalid_candidate_name_ignored`: kandydat `"zła nazwa"` nie tworzy propozycji.
  - `test_applicant_birth_date`: `short_text` z `about_applicant=True` i `semantic=BIRTH_DATE` daje DATEPICKER, `read_only is True`, `default_value == "PESEL.birthDate"` i `default_value_type == "EXTERNAL_SYSTEM"`.
  - `test_editable_mlpz_attribute`: `initial_data="MLPZ.email"` daje `read_only is False` i `default_value == "MLPZ.email"`.
  - `test_unknown_ref_skipped`: `"MLPZ.nope"` daje W09 i `default_value is None`.
  - `test_not_about_applicant_untouched`: pole z `BIRTH_DATE` bez `about_applicant` nie dostaje `default_value`.
- [ ] **Step 2: Uruchom.** Oczekiwane: FAIL.
- [ ] **Step 3: Zaimplementuj.**
- [ ] **Step 4: Uruchom** testy i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 4: `build/states.py`: generator i tester JSONata

**Files:**
- Modify: `backend/app/pipeline/build/states.py`
- Test: `backend/tests/unit/build/test_states.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `@dataclass(frozen=True) FieldLocation(page_title: str, section_tech_name: str, field_tech_name: str, repeating: bool, section_key: str)`.
  - `condition_to_jsonata(cond: Condition, locate: Callable[[str], FieldLocation], *, context_section_key: str | None) -> str` daje kształt jak we wzorcach. Ścieżki `P(loc)`:
    - zwykła sekcja: `tabs['{page}' in title].questions['{sec}' in field.techName].field.repeatingSectionGrid['{fld}' in field.techName].field.__userAnswer`;
    - sekcja powtarzająca, gdy `context_section_key == loc.section_key`: `tabs['{page}' in title].questions['{sec}' in field.techName].field.__userAnswer[$repeatingSectionIndex]['{fld}' in fieldTechName].answers`;
    - sekcja powtarzająca spoza kontekstu → `ValueError`.
  - Atom `A(Eq)` = `"{v}" in P(loc)`. Renderowanie:
    - `Eq` → `(A)`;
    - `Not(Eq)` → `$not(A)`, a `Not(x)` dla złożonego `x` → `$not(R(x))`;
    - `AllOf` → `R(i1) and R(i2)…`, `AnyOf` → `R(i1) or R(i2)…`, przy czym element złożony (AllOf/AnyOf) zagnieżdżony w innym owijamy w nawias.
  - Przykłady, które muszą wyjść 1:1, po usunięciu wszystkich białych znaków z obu stron, ze wzorca N:
    - pole `wybierz_jako_kto_wnioskujesz`;
    - pole `ulica_zagranica` (`$not`);
    - sekcja `pelnomocnictwo` (`or` z zagnieżdżonym `and`).
  - Wartości w `"…"` i tytuły w `'…'` escapujemy tak, żeby JSONata zwracała dokładnie oryginalny tekst. Empirycznie sprawdź escape'y akceptowane przez jsonata-python (`\"`, `\'`, `\\`) i zapisz wynik w docstringu.
  - `query_compiles(query: str) -> str | None`: komunikat błędu albo `None`.
  - `query_references(query: str) -> tuple[set[str], set[str]]`: (tytuły stron, techName) z `'X' in title` oraz `'y' in field.techName` / `'y' in fieldTechName`, z odwróconym escapingiem. Używa tego `verify.py`.
  - `check_condition_query(query: str, cond: Condition, locate: Callable[[str], FieldLocation]) -> bool` (test semantyczny ze spec §8.7):
    1. Dla każdego pola z warunku zbiór kandydatów to wartości z jego `Eq` plus `"__inna_wartosc__"`.
    2. Iloczyn kartezjański, najwyżej 64 kombinacje; dalsze pomijamy.
    3. Dla każdej kombinacji powstaje syntetyczny dokument. Zwykła sekcja: `{"tabs": [{"title", "questions": [{"field": {"techName": sec, "repeatingSectionGrid": [{"field": {"techName": fld, "__userAnswer": [v]}}]}}]}]}`. Sekcja powtarzająca: `section.field.__userAnswer = [[{"fieldTechName": fld, "answers": [v]}, …]]` i `assign("repeatingSectionIndex", 0)`.
    4. Wynik JSONaty porównujemy z ewaluacją `cond` w Pythonie. `True`, gdy wszystkie się zgadzają.
  - `build_states(pages: list[PageNode]) -> tuple[dict[str, list[dict[str, str]]], list[Issue]]`:
    - klucz wyniku to `key` węzła;
    - sekcja z `show_when` → `SHOW`;
    - pole → `SHOW` z `show_when` i `READ_ONLY` z `read_only_when`, a `context_section_key` to sekcja pola;
    - `locate` buduje z `pages` po `assign_unique_tech_names`;
    - nieznany `ref`, `ValueError`, brak kompilacji albo nieudany test semantyczny → stan pominięty z `W06_STATE_REMOVED` i `path` = `key`.

- [ ] **Step 1: Napisz testy w `tests/unit/build/test_states.py`:**
  - `test_matches_reference_queries` (parametryzowany, 3 przypadki): zapytanie wygenerowane dla warunku odpowiadającego polu lub sekcji wzorca N, po `re.sub(r"\s+", "", …)`, równa się zapytaniu ze wzorca. Wzorzec wczytuje test.
  - `test_semantic_check_passes_for_compound`: `AnyOf(Eq, AllOf(Eq, Eq))` na polach z dwóch stron.
  - `test_repeating_section_query`: zapytanie zawiera `$repeatingSectionIndex` i `fieldTechName`, a `check_condition_query` daje True.
  - `test_quotes_in_values_and_titles`: wartość `Wniosek „a” "b" 'c'` i tytuł strony `Strona 'X'`. Zapytanie się kompiluje, `check_condition_query` daje True, a `query_references(q)[0] == {"Strona 'X'"}`.
  - `test_query_compiles_reports_error`: `query_compiles("tabs['x' in ") is not None`.
  - `test_unknown_ref_removed_with_warning`: `build_states` daje brak klucza węzła w wyniku i ostrzeżenie W06.
- [ ] **Step 2: Uruchom.** Oczekiwane: FAIL.
- [ ] **Step 3: Zaimplementuj.**
- [ ] **Step 4: Uruchom** testy i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 5: Szablony sekcji predefiniowanych i `build/sections.py`

**Files:**
- Create: `backend/app/resources/templates/*.json` (lista niżej; usuń `.gitkeep`)
- Modify: `backend/app/pipeline/build/sections.py`
- Test: `backend/tests/unit/build/test_sections.py`

**Format szablonu (JSON):** `{"key", "type", "title", "techName", "descriptionHtml", "fields": [...]}`.

Pole ma klucze takie jak w wyniku: `type`, `title`, `techName`, `options` (lista nazw), `validation`, `readOnly`, `dictionaryName`, `searchEnabled`, `multiLevelTree`, `defaultValue`, `tooltipMessage`. Do tego klucze tylko dla buildera:
- `key`: lokalny, a `instantiate` dodaje prefiks `"{section_key}."`;
- `descriptionHtml`: fragment `<body>`;
- `initialData`: np. `"IDENTITY.name"` albo `"MLPZ.postCode"`;
- `showWhen` / `readOnlyWhen`: warunek `{"eq": [ref, value]} | {"not": c} | {"all": [c…]} | {"any": [c…]}`. `ref` bez kropki jest lokalny, a z kropką bezwzględny.

Placeholdery w stringach: `{sfx}`, `{title}`, `{label}`, `{form_title}`. Treści HTML kopiuj **ze wzorca N**, z tymi zmianami:
- bez `style="…"`, bez `<span>` i bez `<img …>`;
- link z ikoną staje się jednym `<a>` z atrybutami z Global Constraints i `title` jak we wzorcu;
- tytuł przelewu to „{form_title} – opłata skarbowa za pełnomocnictwo”;
- `<pre data-language="plain"></pre>` usuń.

**Szablony.** Kolejność pól = kolejność `y` we wzorcu N.
- **`authority.json`:** sekcja `{title}` / `{techName}` z `TEXT_FIELD` `{label}` (`readOnly`, bez walidacji; `defaultValue` ustawia kod). Warianty:
  - URZAD: tytuł „Urząd, do którego jest składany wniosek”, techName `urzad_do_ktorego_jest_skladany_wniosek`, pole „Nazwa urzędu” / `nazwa_urzedu`;
  - ORGAN: tytuł „Organ, do którego jest składany wniosek”, techName `organ_do_ktorego_jest_skladany_wniosek`, pole „Nazwa organu” / `nazwa_organu`.
- **`applicant_subject.json`:** `podmiot_wniosku` „Podmiot wniosku”:
  - RADIO `wybierz_w_czyim_imieniu_wnioskujesz` „Wybierz, w czyim imieniu wnioskujesz”, REQUIRED (opcje ustawia kod);
  - RADIO `wybierz_jako_kto_wnioskujesz` „Wybierz, jako kto wnioskujesz”: Pełnomocnik, Reprezentant; REQUIRED; `showWhen` eq „Osoby prawnej lub jednostki organizacyjnej”.
- **`your_data.json`:** `twoje_dane` „Twoje dane”: `imie` „Imię”, `nazwisko` „Nazwisko”, `numer_pesel` „Numer PESEL” (+PESEL). Wszystkie REQUIRED, `readOnly`, `initialData` `IDENTITY.name|surname|pesel`.
- **`address.json`:** sekcja `{title}` / `{techName}`. Wszystkie pola REQUIRED poza `numer_lokalu{sfx}`, które jest opcjonalne. Pola:
  - `kraj{sfx}` „Kraj”: SELECT, `Kraje`, `multiLevelTree: false`, `searchEnabled: true`, `defaultValue: ["Polska"]`;
  - `miejscowosc{sfx}_zagranica` „Miejscowość”: showWhen not Polska;
  - `kod_pocztowy{sfx}_zagranica` „Kod pocztowy”: not Polska, bez walidatora formatu;
  - `ulica{sfx}_zagranica` „Ulica”: not Polska;
  - `wojewodztwo{sfx}` z tytułem `TERYT_4G_DOWODOWY`: SELECT, `TERYT_4G_DOWODOWY`, `multiLevelTree: true`, `searchEnabled: true`, `defaultValue: []`, Polska;
  - `kod_pocztowy{sfx}` „Kod pocztowy”: +ZIP_CODE, Polska, `initialData MLPZ.postCode`;
  - `ulica{sfx}` „Ulica”: Polska, `initialData MLPZ.street`;
  - `numer_budynku{sfx}` „Numer budynku”: `MLPZ.building`;
  - `numer_lokalu{sfx}` „Numer lokalu”: `MLPZ.apartment`.
- **`other_person.json`:** `dane_innej_osoby` „Dane innej osoby”: `imie_inna_osoba`, `nazwisko_inna_osoba`, `numer_pesel_inna_osoba` (+PESEL), wszystkie REQUIRED.
- **`entity.json`:** `dane_podmiotu` „Dane podmiotu”:
  - `nazwa` „Nazwa” REQUIRED;
  - `nip` „NIP” REQUIRED+NIP;
  - `regon` „REGON” REQUIRED+REGON;
  - `numer_krs` „Numer KRS”, opcjonalne, `descriptionHtml` `<p>Wpisz 10 cyfr.</p>`.
- **`representative.json`:** `potwierdzenie_ze_jestes_reprezentantem` „Potwierdzenie, że jesteś reprezentantem”:
  - `descriptionHtml` sekcji ze wzorca;
  - FILE_UPLOADER `plik_z_odpisem_danych` „Plik z odpisem danych”, REQUIRED;
  - `descriptionHtml` pola: `<p>Dopuszczalny format pliku: .jpg, .pdf, .png, .jpeg. Maksymalny rozmiar pliku: 10 MB. Maksymalna liczba plików: 3.</p>` (D8, wartości ze zrzutów).
- **`power_of_attorney.json`:** `pelnomocnictwo` „Pełnomocnictwo”:
  - `descriptionHtml` ze wzorca;
  - FILE_UPLOADER `plik_dokumentu_z_pelnomocnictwem` „Plik dokumentu z pełnomocnictwem”, REQUIRED;
  - opis z formatami `.jpg, .pdf, .xml, .PAdES, .png, .jpeg, .CAdES, .XAdES`, 10 MB, 1 plik.
- **`stamp_duty_v1.json`:** `oplata_skarbowa_pelnomocnictwo_1` „Opłata skarbowa”:
  - `descriptionHtml` ze wzorca, z linkiem `https://www.biznes.gov.pl/pl/portal/0089#8`;
  - RADIO `czy_zlozenie_pelnomocnictwa_wymaga_oplaty_skarbowej` „Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?”: Tak, Nie; REQUIRED;
  - TEXT_BLOCK `oplata_info_1` (showWhen Tak), HTML ze wzorca z linkiem `https://warszawa19115.pl/-/oplata-skarbowa`;
  - FILE_UPLOADER `plik_z_potwierdzeniem_przelewu` „Plik z potwierdzeniem przelewu” (showWhen Tak), REQUIRED, opis `.jpg, .pdf, .png, .jpeg`, 10 MB, 1 plik.
- **`stamp_duty_v2.json`:** `oplata_skarbowa_pelnomocnictwo_2` „Opłata skarbowa za pełnomocnictwo”:
  - TEXT_BLOCK `oplata_info` z HTML ze wzorca (z linkiem `…0089#9`);
  - FILE_UPLOADER `plik_z_potwierdzeniem_przelewu_2` jak wyżej.
- **`contact.json`:** `dane_do_kontaktu` „Dane do kontaktu”:
  - `descriptionHtml`: dwa akapity ze wzorca;
  - `numer_telefonu` „Numer telefonu” (`MLPZ.phoneNumber`);
  - `adres_e_mail` „Adres e-mail” (EMAIL, `MLPZ.email`);
  - oba opcjonalne.
- **`preview.json`:** `podglad_uzupelnionego_wniosku` „Podgląd uzupełnionego wniosku” z TEXT_BLOCK `podglad_1`. Tekst zależy od `signed`:
  - podpis: „Zanim przejdziesz do wyboru sposobu podpisu, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji.”;
  - bez podpisu: „Zanim wyślesz formularz, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji.”.

**Interfaces:**
- Consumes: Task 1, `FormDraft`.
- Produces:
  - `@dataclass(frozen=True) BuildOptions(identity_source: Literal["MLPZ","PESEL"] = "MLPZ", finish_page_style: Literal["sample","info_section"] = "sample", max_sections_per_page: int = 8, rodo_clause_url: str | None = None, signed: bool = True, id_factory: Callable[[], str] = lambda: str(uuid.uuid4()))` z `@classmethod from_settings(cls, settings: Settings) -> BuildOptions` (pola `initial_data_identity_source`, `finish_page_style`, `max_sections_per_page`). Klasa jest w `sections.py`, a re-eksport w `build/__init__.py`.
  - `load_template(name: str) -> dict[str, Any]` (`@cache`, `importlib.resources`).
  - `instantiate(template: dict[str, Any], *, key: str, suffix: str = "", params: Mapping[str, str] = {}, initial_data: bool = True, identity_source: str = "MLPZ") -> SectionNode`:
    - placeholdery podstawia w stringach, a wartości `params` escapuje w HTML;
    - klucze pól to `"{key}.{lokalny}"`, warunki JSON przechodzą na IR (lokalne refy → `"{key}.{ref}"`);
    - `IDENTITY.` → `"{identity_source}."`;
    - przy `initial_data=False` usuwa `initialData`.
  - Stałe:
    - `SUBJECT_CHOICE_KEY = "podmiot_wniosku.w_czyim_imieniu"`, `ROLE_CHOICE_KEY = "podmiot_wniosku.jako_kto"`, czyli lokalne klucze `w_czyim_imieniu` i `jako_kto` w szablonie;
    - `APPLICANT_OPTIONS: dict[ApplicantKind, str]` = {SELF: „Swoim”, OTHER_PERSON: „Innej osoby”, LEGAL_ENTITY: „Osoby prawnej lub jednostki organizacyjnej”}.
  - `applicant_page_sections(draft: FormDraft, options: BuildOptions) -> list[SectionNode]`, sekcje w kolejności wzorca:
    1. Urząd lub Organ, z `default_value = authority.name`.
    2. Podmiot wniosku, tylko gdy `set(applicant_kinds) != {SELF}`. Opcje według `applicant_kinds` w kolejności enuma. `jako_kto` tylko przy `LEGAL_ENTITY`.
    3. Twoje dane.
    4. Adresy wnioskodawcy według `addresses` (pusta lista = ZAMIESZKANIA). `initial_data=True` ma tylko pierwszy z nich.
       - „Adres zamieszkania” `adres_zamieszkania`, sfx `""`;
       - „Adres zameldowania” `adres_zameldowania`, sfx `_zameldowanie`;
       - „Adres korespondencyjny” `adres_korespondencyjny`, sfx `_korespondencja`.
    5. Przy LEGAL_ENTITY:
       - Dane podmiotu (SHOW: osoba prawna);
       - „Adres siedziby” `adres_siedziby`, sfx `_siedziba` (SHOW: osoba prawna, bez danych inicjalnych);
       - Potwierdzenie reprezentanta (SHOW: osoba prawna AND Reprezentant).
    6. Przy OTHER_PERSON:
       - Dane innej osoby (SHOW: inna osoba);
       - „Adres zamieszkania innej osoby” `adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem`, sfx `_inna_osoba` (SHOW: inna osoba, bez danych inicjalnych).
    7. Pełnomocnictwo przy OTHER_PERSON lub LEGAL_ENTITY: SHOW = AnyOf dostępnych gałęzi (inna osoba; osoba prawna AND Pełnomocnik). Przy jednej gałęzi sama ta gałąź.
    8. Opłata v1 przy OTHER_PERSON (SHOW: inna osoba).
    9. Opłata v2 przy LEGAL_ENTITY (SHOW: osoba prawna AND Pełnomocnik).
  - `contact_page_sections(draft: FormDraft, options: BuildOptions, extra_attachments: list[str]) -> list[SectionNode]`:
    1. Dane do kontaktu.
    2. Gdy `extra_attachments` niepuste: sekcja „Załączniki” `zalaczniki` z FILE_UPLOADER na każdy załącznik. Pole jest REQUIRED, `tech_name = slugify(nazwa)`, opis „Dopuszczalny format pliku: .jpg, .pdf, .png, .jpeg. Maksymalny rozmiar pliku: 10 MB. Maksymalna liczba plików: 1.”.
    3. Sekcja zgód, a w niej `CONSENT_SECTION` `zgoda` (`title=""`):
       - bez `statements`: „Zgoda” / `zgoda_wyrazenie`, jak wzorzec N;
       - ze `statements`: „Zgody i oświadczenia” / `zgody_i_oswiadczenia`;
       - pierwsza zgoda to RODO: `<p>Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z klauzulą informacyjną</p>`, przy czym „klauzulą informacyjną” jest `external_link`, gdy ustawiono `rodo_clause_url`;
       - potem `statements`, każde escapowane w `<p>`;
       - wszystkie `required=True`, `select_all_enabled=True` przy więcej niż jednej zgodzie.
  - `finish_page_sections(draft: FormDraft, options: BuildOptions) -> list[SectionNode]`:
    - „Podsumowanie” `podsumowanie` z TEXT_BLOCK `podsumowanie_1` z escapowanym `summary_info`, gdy jest ustawione;
    - potem podgląd z `preview.json`;
    - w stylu `info_section` pola TEXT_BLOCK mają typ `INFO_SECTION`.

- [ ] **Step 1: Napisz testy w `tests/unit/build/test_sections.py`:**
  - `test_all_applicant_kinds_section_order`: tytuły sekcji dokładnie jak we wzorcu N: [„Urząd, do którego jest składany wniosek”, „Podmiot wniosku”, „Twoje dane”, „Adres zamieszkania”, „Dane podmiotu”, „Adres siedziby”, „Potwierdzenie, że jesteś reprezentantem”, „Dane innej osoby”, „Adres zamieszkania innej osoby”, „Pełnomocnictwo”, „Opłata skarbowa”, „Opłata skarbowa za pełnomocnictwo”]. `tech_name` sekcji jak we wzorcu.
  - `test_self_only`: [Urząd…, Twoje dane, Adres zamieszkania].
  - `test_person_kinds_only`: opcje radia to [„Swoim”, „Innej osoby”], brak `jako_kto` i brak sekcji podmiotu.
  - `test_organ_authority`: „Organ, do którego jest składany wniosek”, pole „Nazwa organu” z `default_value == "Wójt Gminy Elbląg"` i `read_only is True`.
  - `test_address_fields_match_reference`: `tech_name` pól adresu siedziby to dokładnie [`kraj_siedziba`, `miejscowosc_siedziba_zagranica`, `kod_pocztowy_siedziba_zagranica`, `ulica_siedziba_zagranica`, `wojewodztwo_siedziba`, `kod_pocztowy_siedziba`, `ulica_siedziba`, `numer_budynku_siedziba`, `numer_lokalu_siedziba`]. Żadne z nich nie ma `initial_data`. W adresie zamieszkania `kod_pocztowy` ma `initial_data == "MLPZ.postCode"`.
  - `test_identity_source`: `PESEL` daje `initial_data == "PESEL.name"` dla `imie`.
  - `test_power_of_attorney_condition`: `show_when == AnyOf((Eq(SUBJECT_CHOICE_KEY, "Innej osoby"), AllOf((Eq(SUBJECT_CHOICE_KEY, "Osoby prawnej lub jednostki organizacyjnej"), Eq(ROLE_CHOICE_KEY, "Pełnomocnik")))))`.
  - `test_form_title_escaped_in_stamp_duty`: tytuł `Wniosek <b>` daje `Wniosek &lt;b&gt;` w HTML opłaty, a HTML nie zawiera `<img` ani `style=`.
  - `test_consents`: bez `statements` jest „Zgoda” i 1 zgoda. Z 2 `statements` są „Zgody i oświadczenia”, 3 zgody i `select_all_enabled`. Przy `rodo_clause_url` zgoda zawiera `href="https://…"`.
  - `test_finish_info_section_style`: przy `info_section` wszystkie pola mają typ INFO_SECTION.
  - `test_every_template_instantiates`: każdy plik z `resources/templates` przechodzi przez `instantiate`.
- [ ] **Step 2: Uruchom.** Oczekiwane: FAIL.
- [ ] **Step 3: Zaimplementuj** szablony i `sections.py`.
- [ ] **Step 4: Uruchom** testy i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 6: `verify.py`: JSON Schema, R01–R15, autonaprawa

**Files:**
- Modify: `backend/app/pipeline/verify.py`
- Test: `backend/tests/unit/test_verify.py`

**Interfaces:**
- Consumes: Task 1 (`models.form.*`, `issues.*`, `catalogs.*`) i Task 4 (`states.query_compiles`, `states.query_references`; jeśli ich jeszcze nie ma, pisz przeciw sygnaturom).
- Produces:
  - `@dataclass VerifyResult(form: FormDefinition, errors: list[Issue], warnings: list[Issue], fixes: list[Issue])` z property `valid` (`not errors`).
  - `verify_form(form: Mapping[str, Any], *, autofix: bool = True, id_factory: Callable[[], str] = lambda: str(uuid.uuid4())) -> VerifyResult`:
    - nigdy nie rzuca wyjątku na danych wejściowych; przy złej strukturze, np. `tabs` niebędącym listą, daje `SCHEMA`;
    - pracuje na `copy.deepcopy`.
- Zachowanie:
  - **Kolejność:** autonaprawy (gdy `autofix`), potem schemat, potem reguły. Każda naprawa trafia do `fixes` z kodem reguły.
  - **`path`:** w formacie `tabs[1].questions[0].field.repeatingSectionGrid[2]`.
  - **Autonaprawy:**
    - brakujące klucze bazowe → wartości puste, przy czym sekcji brakujący `description` ustawiamy na `EMPTY_HTML` (R06 dla `validation`); `validation`, które nie jest listą (wzorzec P ma `{}`), → `[]` (R06);
    - pole niebędące sekcją na poziomie strony → opakowanie w `SECTION` z tytułem i `techName` pola plus `"_sekcja"` (R03);
    - sekcja w sekcji → przeniesienie jej pól do rodzica (R04);
    - pusta strona → usunięcie (R03_EMPTY_PAGE);
    - zduplikowany `techName` → `_2`, `_3` (R12);
    - zduplikowane albo puste `id` → `id_factory()` (R12);
    - stan z nieznanym `type`, bez kompilacji albo z odwołaniem do nieistniejącego tytułu strony lub `techName` → usunięcie z ostrzeżeniem `W06_STATE_REMOVED` (R11);
    - stan inny niż SHOW na sekcji → usunięcie (R11);
    - niedozwolony walidator → usunięcie (R15);
    - `dictionaryName` w typie spoza `CHOICE_TYPES` → usunięcie klucza (R08);
    - pole ze słownikiem i niepustymi `options` → `options=[]` (R08);
    - `flow` niespójny z R07 → przebudowa liniowa w kolejności `tabs` z nowymi `id` (R07).
  - **Reguły zgłaszane jako błędy:**
    - R01: pusty tytuł albo dłuższy niż 255 znaków. Brak prefiksu daje tylko ostrzeżenie `W05_TITLE_PREFIX`.
    - R02: co najmniej 2 strony, dokładnie jedna FINISH i to ostatnia, pozostałe MAIN.
    - R03, R04.
    - R05: na FINISH tylko TEXT_BLOCK i INFO_SECTION w sekcjach.
    - R06: `validation` to lista.
    - R07: z pierwszej strony po `links` dochodzimy do FINISH, każda strona jest osiągalna, `source` i `target` istnieją.
    - R08, R09: pole wyboru bez słownika ma co najmniej 2 opcje, CHECKBOX co najmniej 1.
    - R10: `defaultValueType == EXTERNAL_SYSTEM` wymaga refu z katalogu. `readOnly` jest wymagane, chyba że atrybut jest `editable`.
    - R11, R12.
    - R13: CONSENT_SECTION ma co najmniej 1 zgodę z niepustym `description` i boolowskim `required`.
    - R14: INFO_SECTION ma niepusty `description`.
    - R15.
    - Nieznany `type` pola daje `SCHEMA` z komunikatem „Nieznany typ pola”.
  - Jedna funkcja na regułę lub naprawę, a `verify_form` to lista wywołań.

- [ ] **Step 1: Napisz testy w `tests/unit/test_verify.py`:**
  - `test_minimal_valid_form`: 2 strony (MAIN z sekcją i TEXT_FIELD, FINISH z sekcją i TEXT_BLOCK) i jeden link dają `valid` oraz `fixes == []`.
  - `test_broken_manual_json`: TEXT_FIELD bezpośrednio na stronie, bez `validation`, dwa pola o tym samym `id` i `techName`, pusta trzecia strona MAIN, bez `flow`.
    - `autofix=False`: kody `errors` obejmują R03_FIELD_OUTSIDE_SECTION, R06_REQUIREDNESS, R12_DUPLICATE_ID, R12_DUPLICATE_TECH_NAME, R03_EMPTY_PAGE i R07_FLOW;
    - `autofix=True`: wynik jest `valid`, a `verify_form(result.form, autofix=False).valid` daje True.
  - `test_reference_samples_are_repairable` (parametryzowany po obu wzorcach): `autofix=True` daje `valid`. Dla wzorca P w `fixes` jest R06 (`validation: {}`, brak `states`).
  - `test_state_with_unknown_tech_name_removed`: ostrzeżenie W06, a `states == []`.
  - `test_disallowed_validator_removed`: NUMBER z `["REQUIRED","PESEL"]` daje `["REQUIRED"]`.
  - `test_finish_input_is_error`: TEXT_FIELD na FINISH daje R05 także przy `autofix=True`.
  - `test_initial_data_rules`: `EXTERNAL_SYSTEM` + `MLPZ.name` bez `readOnly` daje R10. `MLPZ.email` bez `readOnly` nie daje błędu. `MLPZ.nope` daje R10.
  - `test_garbage_input`: `verify_form({"tabs": 5})` daje `SCHEMA` bez wyjątku.
  - `test_title_prefix_is_warning`: tytuł „Karta” daje W05 i `valid`.
- [ ] **Step 2: Uruchom.** Oczekiwane: FAIL.
- [ ] **Step 3: Zaimplementuj.**
- [ ] **Step 4: Uruchom** testy i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 7: `pages.py`, `layout.py`, `serialize.py`, `build/__init__.py`: orkiestracja

**Files:**
- Modify: `backend/app/pipeline/build/pages.py`, `backend/app/pipeline/build/layout.py`, `backend/app/pipeline/build/__init__.py`
- Create: `backend/app/pipeline/build/serialize.py`
- Test: `backend/tests/unit/build/test_build.py`

**Interfaces:**
- Consumes: Task 1–6.
- Produces (`pages.py`):
  - `subject_pages(draft: FormDraft, options: BuildOptions) -> tuple[list[PageNode], list[Issue]]`:
    - `DraftPage` → `PageNode(MAIN, key="p{i}")`;
    - `DraftSection` → `SectionNode`: `REPEATING_SECTION`, gdy `repeating`; `tech_name = slugify(title)`; `description_html = paragraphs(description)`; `pending_show_when`;
    - pola przez `map_draft_field(key="p{i}.s{j}.f{k}")`;
    - pole z `about_applicant` i semantyką z `PREDEFINED_APPLICANT_SEMANTICS` jest pomijane z `W04_DUPLICATE_PREDEFINED_FIELD`;
    - pusta sekcja jest pomijana;
    - podział stron według `max_sections_per_page`, z tytułami jak w „Decyzjach”.
  - `resolve_pending_conditions(pages: list[PageNode]) -> list[Issue]`:
    - `pending_*` zamienia na `show_when` / `read_only_when` przez `convert_condition`;
    - dopasowanie etykiety po `casefold()` i zwiniętych białych znakach, w kolejności: ta sama sekcja, ta sama strona, cały formularz;
    - brak dopasowania daje `W03_CONDITION_UNRESOLVED` z `path` = `key`.
  - `flow_links(tab_ids: list[str], id_factory: Callable[[], str]) -> list[dict[str, str]]`: linki liniowe `{"id", "source", "target"}`.
- Produces (`layout.py`):
  - `@dataclass(frozen=True) Placement(x: int, y: int, rows: int, cols: int)`;
  - `compute_layout(pages: list[PageNode]) -> dict[str, Placement]` (klucz to `key` węzła), według „Decyzji”. `questionOrder` w serializacji = `y`.
- Produces (`serialize.py`): `to_form_definition(title: str, pages: list[PageNode], states: dict[str, list[dict[str, str]]], id_factory: Callable[[], str]) -> FormDefinition`:
  - wynik: `{"title", "tabs": [{"id", "title", "type", "questions": [{"x","y","rows","cols","field": {...}}]}], "flow": {"links": [...]}}`;
  - pola sekcji trafiają do `repeatingSectionGrid` sekcji (także w `SECTION`, jak we wzorcach);
  - `options` → `[{"id": n, "name": n, "techName": slugify(n)}]`;
  - `description` sekcji to zawsze `html_document(description_html)`, a pola `html_document(...)` tylko gdy niepusty, w przeciwnym razie `""`;
  - `consentSectionConfig` → `{"consents": [{"description": html_document(c.description_html), "required": c.required}], "files": []}`;
  - klucze opcjonalne wpisujemy według Global Constraints.
- Produces (`build/__init__.py`):
  - `@dataclass BuildResult(form: FormDefinition, warnings: list[Issue], dictionary_proposals: list[DictionaryProposal])`.
  - `build_form(draft: FormDraft, options: BuildOptions = BuildOptions()) -> BuildResult`, w kolejności:
    1. `normalize_title`.
    2. Strona `PageNode("dane", "Dane", MAIN, applicant_page_sections(...))`.
    3. `subject_pages`.
    4. Strona „Kontakt i zgody” z `contact_page_sections`. Dostaje załączniki ze szkicu, których znormalizowanej etykiety nie ma wśród pól FILE_UPLOADER. Te pomijamy z `W10_ATTACHMENT_DUPLICATE`.
    5. Strona „Strona końcowa” (FINISH).
    6. `resolve_pending_conditions`.
    7. `assign_unique_tech_names`.
    8. `apply_dictionaries`.
    9. `apply_initial_data`.
    10. `build_states`.
    11. `to_form_definition`.
    Ostrzeżenia zbiera po kolei. Re-eksport: `BuildOptions`, `BuildResult`, `DictionaryProposal`, `build_form`, `build_fallback`.
  - `build_fallback(title: str | None = None, authority_name: str = "", options: BuildOptions = BuildOptions()) -> BuildResult`:
    - buduje szkic `FormDraft(title=title or "Wniosek", authority=Authority(name=authority_name), applicant_kinds=[SELF, OTHER_PERSON], subject_pages=[DraftPage(title="Treść wniosku", sections=[DraftSection(title="Treść wniosku", fields=[DraftField(label="Treść wniosku", kind=long_text, required=True)])])])`;
    - wywołuje `build_form` i na początek `warnings` dodaje `W01_LLM_FALLBACK`.

- [ ] **Step 1: Napisz testy w `tests/unit/build/test_build.py`.** Wspólna fixture to deterministyczny `id_factory` (licznik).
  - `test_minimal_draft`: `FormDraft(title="Wniosek o X", applicant_kinds=[SELF])` daje 3 strony, brak sekcji `podmiot_wniosku`, `verify_form(form, autofix=False).valid`.
  - `test_unresolved_condition_is_dropped_with_warning`: `visible_when` do „Nie ma mnie” daje W03 i `states == []`.
  - `test_duplicate_labels_resolve_nearest`: na stronie przedmiotu pole „Ulica” z `read_only_when` do checkboxa „Brak nazwy ulicy” w tej samej sekcji. Wynik: `techName` pola to `ulica_2`, stan READ_ONLY, a zapytanie zawiera `'brak_nazwy_ulicy' in field.techName` i tytuł strony przedmiotu.
  - `test_applicant_semantics`: pole z `about_applicant` i `semantic=PESEL` jest pominięte (W04). Pole z `semantic=BIRTH_DATE` ma `defaultValue == "PESEL.birthDate"`.
  - `test_attachment_duplicate_skipped`: załącznik o etykiecie istniejącego FILE_UPLOADER-a daje W10 i brak sekcji `zalaczniki`.
  - `test_fallback`: `build_fallback("Wniosek o Y")` ma W01 jako pierwsze ostrzeżenie, a wynik jest `valid`.
  - `test_deterministic`: dwa `build_form` z licznikiem dają identyczny JSON.
  - `test_layout`: na stronie „Dane” `y` pierwszej sekcji to 0, kolejne rosną o `rows` poprzedniej. `questionOrder == y` dla sekcji i pól, a `rows` sekcji = liczba pól + 1.
  - `test_every_field_has_base_keys`: każdy `field` ma klucze w kolejności `BASE_FIELD_KEYS` na początku.
  - `test_page_split`: 10 sekcji przy `max_sections_per_page=4` daje strony „X”, „X (cd.)”, „X (cd. 2)”.
- [ ] **Step 2: Uruchom.** Oczekiwane: FAIL.
- [ ] **Step 3: Zaimplementuj.**
- [ ] **Step 4: Uruchom** testy i polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 8: Golden: wynik buildera kontra wzorce

**Files:**
- Create: `backend/tests/golden/drafts/nadplata.json`, `backend/tests/golden/drafts/numer_porzadkowy.json` (szkice `FormDraft` w camelCase, odtwarzające wzorce)
- Create: `backend/tests/golden/test_reference_forms.py`

**Interfaces:**
- Consumes: `build_form`, `verify_form`, wzorce z `wymagania/`.
- Szkice:
  - **nadplata:** `authority` URZAD „Urząd Gminy Ulan-Majorat”, wszystkie trzy `applicant_kinds`, `identity_source="PESEL"` w opcjach testu. Strona „Informacje o nadpłacie” z sekcjami jak we wzorcu N:
    - „Informacje o nadpłacie”: `podatek_ktorego_dotyczy_nadplata` (short_text), `kwota` (number), `uzasadnienie` (long_text z opisem);
    - „Rozliczenie nadpłaty”: radio + 2 pola z `visible_when`;
    - „Korekta deklaracji”: opis sekcji + file.
  - **numer_porzadkowy:** ORGAN „Wójt Gminy Elbląg”, strona „Informacje o budynku” z sekcją „Lokalizacja budynku”: Miejscowość, Ulica, Numer ewidencyjny działki, Obręb.

- [ ] **Step 1: Napisz `test_reference_forms.py`** (parametryzowany po parze szkic + wzorzec):
  - `test_structure_matches_reference`:
    - tytuły tabs są takie jak we wzorcu, poza ostatnią stroną MAIN (wzorzec P ma „Kontakt z urzędem”, my „Kontakt i zgody”: znane odstępstwo);
    - typy tabs się zgadzają;
    - lista `techName` sekcji na każdej stronie jest równa wzorcowi, z wyjątkiem `zgoda_sekcja` → `zgoda_wyrazenie` we wzorcu P.
  - `test_field_coverage`: dla każdej sekcji zbiór `(techName, type)` pól wzorca jest podzbiorem wyniku. Wyjątki są jawne w stałej `KNOWN_DEVIATIONS` z komentarzem. Spodziewane:
    - we wzorcu P `obreb_numer` i `ulica_budynku` to nazwy nadane ręcznie, a nasz slug daje `obreb` i `ulica_2`;
    - pokrycie musi wynieść 100% poza `KNOWN_DEVIATIONS`.
  - `test_states_match_reference`: dla każdego pola i sekcji wzorca, które mają stan, nasz stan ma ten sam `type`, a `query` po usunięciu białych znaków jest równe wzorcowemu. Wyjątki: pola sekcji opłaty z tytułem przelewu i sekcje z `KNOWN_DEVIATIONS`.
  - `test_initial_data_match_reference`: `defaultValue` i `defaultValueType` pól z `EXTERNAL_SYSTEM` we wzorcu są równe naszym.
  - `test_output_is_valid`: `verify_form(form, autofix=False).valid`.
  - Wynik zapisz do `out/golden/<nazwa>.json` tylko przy zmiennej `GOLDEN_WRITE=1`. Domyślnie test niczego nie zapisuje.
- [ ] **Step 2: Uruchom** `uv run pytest tests/golden -q` i napraw szablony lub builder, aż przejdzie. Każde nowe odstępstwo dopisz do `KNOWN_DEVIATIONS` z uzasadnieniem i zgłoś leadowi.
- [ ] **Step 3: Uruchom** polecenia z Global Constraints. Oczekiwane: zielone.

---

### Task 9 (lead): przegląd i dokumentacja

**Files:**
- Modify: `docs/specyfikacja-techniczna.md`:
  - §4.2: dopisz `issues.py`, `build/ir.py`, `build/html.py`, `build/catalogs.py`, `build/serialize.py`;
  - §7.4: dopisz decyzje z „Decyzji” tego planu, które zmieniają spec (D9, adres bez checkboxów, `questionOrder = y`, opisy pól w HTML).

- [ ] **Step 1:** Po każdym zadaniu przejrzyj diff pod kątem Interfaces i Global Constraints, uruchom testy, zrób commit (`git-commit-messages`).
- [ ] **Step 2:** Po Task 8 przejrzyj wygenerowany JSON nadpłaty obok wzorca N.
- [ ] **Step 3:** Zaktualizuj spec i zrób commit `docs`. Raport dla użytkownika.
