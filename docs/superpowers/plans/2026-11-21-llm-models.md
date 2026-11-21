# Modele danych i analiza LLM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kontrakty `DocumentModel` / `FormDraft` / `FormDefinition` oraz krok [4] pipeline'u: `analyze()` wołające lokalną Ollamę (tryby `accurate`/`fast`) i zwracające szkic albo sygnał fallbacku.

**Architecture:** Modele Pydantic v2 w `app/models/`. `FormDraft` jest płaskim schematem dla structured output Ollamy. `FormDefinition` odwzorowuje 1:1 wzorcowy JSON COI. Klient HTTP Ollamy (`pipeline/llm_client.py`) jest za protokołem `LlmClient`, żeby testy podstawiały fałszywy klient. `analyze.py` orkiestruje: prompt → wywołanie → walidacja → (ponowna próba) → normalizacja (`pipeline/draft_normalize.py`); długie dokumenty dzieli i łączy `pipeline/draft_merge.py`.

**Tech Stack:** Python 3.14, Pydantic 2.14, httpx 0.28 (`MockTransport` w testach), FastAPI 0.165, pytest + pytest-asyncio 1.5, Ollama 0.40.16, qwen3:8b / qwen3:4b.

**Spec:** `docs/superpowers/specs/2026-11-21-llm-models-design.md` (projekt zespołu: `docs/specyfikacja-techniczna.md`)

## Global Constraints

- Python 3.14, `mypy --strict` (plugin pydantic) i `ruff check` (konfiguracja z `backend/pyproject.toml`, linia 100) bez błędów po każdym tasku.
- **Żadnych nowych zależności runtime.** httpx, pydantic, fastapi już są.
- Polecenia z katalogu `backend/`: `uv run pytest`, `uv run mypy app`, `uv run ruff check app tests`.
- Docstringi i komunikaty (ostrzeżenia, błędy dla modelu) po polsku. Identyfikatory w kodzie po angielsku.
- Commity: jedna linia w formacie conventional commits, **bez linii `Co-Authored-By`**.
- Nie dotykać `frontend/` ani `pipeline/build/*`, `pipeline/extract/*`.
- LLM: `think: false`, `stream: false`, `temperature`/`seed`/`num_ctx` z `Settings`, `keep_alive: "30m"`.
- Schemat `FormDraft` dla LLM: bez rekurencji i bez `null` (żadnego `anyOf` z `{"type": "null"}`).
- `analyze()` nie rzuca wyjątków z powodu modelu (timeout, sieć, HTTP, zła odpowiedź) – zawsze zwraca `AnalysisResult`.

## Review Focus

1. **Warunek wskazujący pole, które normalizacja zamieniła z wyboru na `short_text`** – szkic musi pozostać poprawny, warunek usunięty z ostrzeżeniem → test `test_condition_on_downgraded_choice_is_dropped` w Task 7.
2. **Ucięty lub niebędący JSON-em tekst od modelu** (przepełnienie kontekstu) – traktowany jak niepoprawny szkic, bez wyjątku → test `test_truncated_json_is_invalid_output` w Task 6.
3. **Budżet żądania prawie wyczerpany przed analizą** (czekanie na semafor) – natychmiastowy fallback bez wołania modelu → test `test_exhausted_deadline_skips_llm` w Task 6.
4. **Dokument pusty albo zawierający tylko klauzulę RODO** – brak wywołania modelu, fallback `empty_document` → test `test_empty_document_falls_back` w Task 6.
5. **Model trybu nie jest pobrany w Ollamie** (instalacja bez `qwen3:4b`) – fallback `unavailable`, nie HTTP 500 → test `test_missing_model_raises_unavailable` w Task 5 i `test_unavailable_falls_back` w Task 6.

---

### Task 1: `ConversionWarning` i `FormDraft`

**Files:**
- Create: `backend/app/models/warning.py`
- Modify: `backend/app/models/draft.py`
- Test: `backend/tests/unit/test_draft.py`

**Interfaces:**
- Produces:
  - `ConversionWarning(BaseModel, frozen)`: `code: str` (wzorzec `^W\d{2}_[A-Z0-9_]+$`), `message: str`, `path: str | None = None`.
  - Literale: `FieldKind = Literal["single_choice","multi_choice","short_text","long_text","number","date","file","info"]`, `ApplicantKind = Literal["SELF","OTHER_PERSON","LEGAL_ENTITY"]`, `AuthorityKind = Literal["URZAD","ORGAN"]`, `ConditionOp = Literal["equals","not_equals"]`.
  - `Condition(field_id: str, op: ConditionOp, value: str)`.
  - `DraftField(id: str, label: str, kind: FieldKind, required: bool, options: list[str] = [], visible_when: list[Condition] = [])`.
  - `DraftSection(title: str, repeating: bool, fields: list[DraftField])` (min. 1 pole).
  - `DraftPage(title: str, sections: list[DraftSection])`.
  - `FormDraft(title: str, authority_kind, authority_name: str, applicant_kinds: list[ApplicantKind], attachments: list[str] = [], statements: list[str] = [], subject_pages: list[DraftPage])`.
  - `FormDraft.iter_fields() -> Iterator[tuple[str, DraftField]]` – ścieżka w formacie `subject_pages[0].sections[1].fields[2]`.
  - `llm_schema() -> dict[str, Any]` = `FormDraft.model_json_schema()`.
- Wszystkie modele szkicu: `ConfigDict(extra="forbid")` (daje `additionalProperties: false` w schemacie). Krótkie `Field(description=...)` po polsku.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_draft.py`)

Pomocnik `_draft(**overrides) -> dict` budujący poprawny szkic Wniosku 1: tytuł „Wniosek o ustalenie numeru porządkowego nieruchomości”, `ORGAN` / „Wójt Gminy Elbląg”, `["SELF","OTHER_PERSON"]`, strona „Informacje o budynku” z sekcją „Lokalizacja budynku” i polami f1–f4 (Miejscowość, Ulica, Numer ewidencyjny działki, Obręb; `short_text`, `required=True`), plus pole f5 `single_choice` „Czy budynek jest w budowie?” z opcjami `["Tak","Nie"]` i f6 `short_text` „Data rozpoczęcia budowy” z `visible_when=[{"field_id":"f5","op":"equals","value":"Tak"}]`.

```python
def test_valid_draft_parses() -> None:
    draft = FormDraft.model_validate(_draft())
    assert [p for p, _ in draft.iter_fields()][0] == "subject_pages[0].sections[0].fields[0]"

def test_optional_lists_default_empty() -> None:  # model może pominąć klucze
    d = _draft(); del d["attachments"]; del d["statements"]
    del d["subject_pages"][0]["sections"][0]["fields"][0]["options"]
    assert FormDraft.model_validate(d).attachments == []

@pytest.mark.parametrize("mutate, fragment", [
    (dup_id, "f1"),                       # dwa pola z id f1 → komunikat zawiera "f1"
    (cond_to_missing("f9"), "f9"),        # warunek na nieistniejące pole
    (cond_to_non_choice("f1"), "f1"),     # warunek na pole tekstowe
    (cond_to_self, "f6"),                 # warunek pola na samym sobie
    (cond_value("Może"), "Może"),         # wartość spoza options
    (applicant_kinds([]), "applicant_kinds"),
    (applicant_kinds(["SELF","SELF"]), "applicant_kinds"),
    (title("  "), "title"),
    (empty_section, "fields"),
])
def test_invalid_draft_rejected(mutate, fragment) -> None:
    with pytest.raises(ValidationError) as exc:
        FormDraft.model_validate(mutate(_draft()))
    assert fragment in str(exc.value)

def test_extra_keys_rejected() -> None:  # model nie może dopisać "semantic"
    d = _draft(); d["subject_pages"][0]["sections"][0]["fields"][0]["semantic"] = "PESEL"
    with pytest.raises(ValidationError): FormDraft.model_validate(d)

def test_llm_schema_is_flat_and_non_nullable() -> None:
    text = json.dumps(llm_schema())
    assert '"null"' not in text
    defs = llm_schema()["$defs"]
    for name, schema in defs.items():  # brak rekurencji: definicja nie odwołuje się do siebie
        assert f"#/$defs/{name}" not in json.dumps(schema)

def test_warning_code_format() -> None:
    ConversionWarning(code="W01_LLM_FALLBACK", message="x")
    with pytest.raises(ValidationError): ConversionWarning(code="llm", message="x")
```

(`dup_id`, `cond_to_missing` itd. to małe funkcje modyfikujące słownik – nazwy wedle uznania.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_draft.py -v`
Expected: FAIL (`ImportError`: brak `FormDraft`).

- [ ] **Step 3: Implement `warning.py` i `draft.py`**

Walidacja krzyżowa w jednym `@model_validator(mode="after")` na `FormDraft`. Błędy jako `ValueError` z komunikatem po polsku, zawierającym id pola i ścieżkę (te komunikaty trafiają do modelu w ponownej próbie), np. `"subject_pages[0].sections[0].fields[5].visible_when: pole f9 nie istnieje"`. `title`/`authority_name`: `str` z `min_length=1` po `strip` (walidator `field_validator`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_draft.py -v && uv run mypy app && uv run ruff check app tests`
Expected: wszystko PASS, brak błędów.

- [ ] **Step 5: Commit**

```bash
git add app/models/warning.py app/models/draft.py tests/unit/test_draft.py
git commit -m "feat(models): FormDraft schema with cross-field validation"
```

---

### Task 2: `FormDefinition`

**Files:**
- Modify: `backend/app/models/form.py`
- Create: `backend/tests/fixtures/form/excerpt.json`
- Test: `backend/tests/unit/test_form.py`

**Interfaces:**
- Produces: `FieldType(StrEnum)` (13 wartości ze spec §5.3), `Validator(StrEnum)` (`REQUIRED, EMAIL, PESEL, NIP, REGON, ZIP_CODE, EPUAP, ADE, SERIAL_NUMBER_ID_CARD`), `Option`, `State(type: Literal["SHOW","READ_ONLY"], query: str)`, `Consent(description: str)`, `ConsentSectionConfig(consents, required, files: list[dict[str, Any]] = [])`, `Field`, `Question(x, y, rows, cols: int, field: Field)`, `Tab(id, title, type: Literal["MAIN","FINISH"], questions)`, `FlowLink(id, source, target)`, `Flow(links)`, `FormDefinition(title, tabs, flow)`, `FormDefinition.to_import_json() -> dict[str, Any]`.
- `Field` – klucze bazowe z domyślnymi pustymi wartościami: `id: str`, `type: FieldType`, `tech_name: str`, `title: str = ""`, `description: str = ""`, `options: list[Option] = []`, `validation: list[Validator] = []`, `read_only: bool = False`, `repeating_section_grid: list[Question] = []`, `states: list[State] = []`, `question_order: int = 0`, `tooltip_message: str = ""`. Klucze dodatkowe domyślnie `None`: `default_value: str | list[str] | None`, `default_value_type: Literal["EXTERNAL_SYSTEM"] | None`, `dictionary_name`, `search_enabled`, `multi_level_tree`, `consent_section_config`, `select_all_enabled`.
- Wspólna baza `_CoiModel`: `ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")`.

- [ ] **Step 1: Wygeneruj fixture wycinka wzorca**

Jednorazowy skrypt (nie commitować skryptu): z `../materials/wniosek-1/konfiguracja_form_wniosekOUstalenieNumeruPorządkowegoNieruchomości (1).json` weź `title`, `tabs[1:]` (Informacje o budynku, Kontakt z urzędem, Strona końcowa) i te `flow.links`, których `source` i `target` należą do tych zakładek. Zapisz do `tests/fixtures/form/excerpt.json` (UTF-8, `ensure_ascii=False`, indent 2).

- [ ] **Step 2: Write the failing tests** (`tests/unit/test_form.py`)

```python
def _assert_roundtrip(source: dict[str, Any]) -> None:
    out = FormDefinition.model_validate(source).to_import_json()
    assert _with_base_defaults(source) == out

def test_excerpt_roundtrip() -> None: _assert_roundtrip(_load("fixtures/form/excerpt.json"))

@pytest.mark.skipif(not MATERIALS, reason="brak COI_MATERIALS_DIR")
def test_full_golden_roundtrip() -> None:  # każdy konfiguracja_form_*.json w COI_MATERIALS_DIR (rekurencyjnie)
    ...

def test_base_keys_always_present() -> None:
    f = Field(id="u", type=FieldType.TEXT_FIELD, tech_name="imie")
    out = FormDefinition(title="t", tabs=[Tab(id="a", title="A", type="MAIN",
          questions=[Question(x=0, y=0, rows=1, cols=3, field=f)])],
          flow=Flow(links=[])).to_import_json()
    field = out["tabs"][0]["questions"][0]["field"]
    assert set(field) == {"id","type","techName","title","description","options","validation",
                          "readOnly","repeatingSectionGrid","states","questionOrder","tooltipMessage"}

def test_default_value_list_for_select() -> None:  # D5
    f = Field(id="u", type=FieldType.SELECT, tech_name="kraj", default_value=["Polska"], dictionary_name="Kraje")
    assert f.model_dump(by_alias=True, exclude_none=True)["defaultValue"] == ["Polska"]

def test_unknown_validator_rejected() -> None:
    with pytest.raises(ValidationError): Field(id="u", type="TEXT_FIELD", tech_name="x", validation=["PHONE"])
```

`_with_base_defaults(d)`: kopia, w której każdemu obiektowi `field` brakujące klucze bazowe są uzupełnione pustymi wartościami (`""`, `[]`, `False`, `0`) – decyzja ze spec §5.8. `MATERIALS = os.environ.get("COI_MATERIALS_DIR")`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_form.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 4: Implement `form.py`**

`to_import_json()` = `self.model_dump(by_alias=True, exclude_none=True, mode="json")`. Jeśli wzorzec ma klucz spoza modelu, **dopisz go do modelu** (nie luzuj `extra="forbid"`).

- [ ] **Step 5: Run tests (w tym pełny wzorzec)**

Run: `COI_MATERIALS_DIR=../materials uv run pytest tests/unit/test_form.py -v && uv run mypy app && uv run ruff check app tests`
Expected: wszystko PASS, w tym `test_full_golden_roundtrip` (nie SKIPPED).

- [ ] **Step 6: Commit**

```bash
git add app/models/form.py tests/unit/test_form.py tests/fixtures/form/excerpt.json
git commit -m "feat(models): FormDefinition mirroring COI import format"
```

---

### Task 3: `DocumentModel` i `to_prompt_text()`

**Files:**
- Modify: `backend/app/models/document.py`
- Create: `backend/tests/fixtures/documents/wniosek1.json`
- Test: `backend/tests/unit/test_document.py`

**Interfaces:**
- Produces: `BlockKind = Literal["heading","paragraph","label","input_placeholder","checkbox_option","table","table_cell"]`, `ExtractionMethod = Literal["pdf_text","ocr","docx","xlsx"]`, `BBox(x0, y0, x1, y1: float)`, `TablePos(row: int ≥ 0, col: int ≥ 0)`, `Block(id: str, kind: BlockKind, text: str, bbox: BBox | None = None, ocr_confidence: float | None = None (0–1), table: TablePos | None = None)`, `Page(number: int ≥ 1, blocks: list[Block])`, `SourceInfo(method: ExtractionMethod, pages: int ≥ 1)`, `DocumentModel(source: SourceInfo, pages: list[Page])`.
- Metody: `iter_blocks() -> Iterator[Block]`, `ocr_mean_confidence: float | None` (property; średnia z nie-`None`), `to_prompt_text(exclude_boilerplate: bool = True) -> str`.
- Walidacja: `id` bloków unikalne w dokumencie; `table_cell` musi mieć `table`.

Reguły renderowania (`to_prompt_text`):
- przed blokami strony `N`: linia `=== strona N`;
- `heading` → `[NAGŁÓWEK] {text}`; `checkbox_option` → `[OPCJA] {text}`; `input_placeholder` → `[POLE]`; `paragraph`/`label` → `{text}`;
- w każdym tekście ciągi `[.…_]{3,}` (także mieszane, np. `……….…`) → ` [POLE] `, potem zwinięcie białych znaków do jednej spacji;
- `table` otwiera tabelę: `[TABELA]`, następujące po nim `table_cell` grupowane po `table.row` (w kolejności `col`, łączone ` | `), zamknięcie `[/TABELA]` przed pierwszym blokiem innego rodzaju lub na końcu strony;
- `exclude_boilerplate`: blok `heading` lub `paragraph`, którego tekst pasuje do `(?i)klauzula informacyjna|\bRODO\b|ochron\w* danych osobowych`, rozpoczyna pomijanie; pomijanie trwa (także przez granice stron) do następnego `heading`, który do wzorca nie pasuje;
- puste linie usuwane, wynik bez końcowego `\n`.

- [ ] **Step 1: Wygeneruj fixture Wniosku 1**

Jednorazowy skrypt (nie commitować): z `../materials/wniosek-1/Wniosek o ustalenie numeru porządkowego nieruchomości.docx` (python-docx, kolejność elementów body) zbuduj `DocumentModel`: akapity niepuste → `paragraph` (akapity z „KLAUZULA INFORMACYJNA” i „WNIOSEK O USTALENIE…” → `heading`), tabele → `table` + `table_cell`; `source.method="docx"`, jedna strona; id `b1…`. Zapisz `model_dump_json(indent=2)` do `tests/fixtures/documents/wniosek1.json`. Plik zawiera tylko dane urzędu (publiczny blankiet) – sprawdź, że nie ma danych osobowych.

- [ ] **Step 2: Write the failing tests** (`tests/unit/test_document.py`)

```python
def test_fill_runs_become_field_markers() -> None:
    doc = _doc([_p("w miejscowości……………….……………… przy ulicy1)…………")])
    assert doc.to_prompt_text() == "=== strona 1\nw miejscowości [POLE] przy ulicy1) [POLE]"

def test_markers_per_kind() -> None:
    doc = _doc([_h("Dane"), _b("checkbox_option", "Tak"), _b("input_placeholder", "....")])
    assert doc.to_prompt_text().splitlines()[1:] == ["[NAGŁÓWEK] Dane", "[OPCJA] Tak", "[POLE]"]

def test_table_rendering() -> None:
    doc = _doc([_b("table", ""), _cell(0, 0, "Imię"), _cell(0, 1, ""), _cell(1, 0, "Nazwisko"), _cell(1, 1, "")])
    assert doc.to_prompt_text().splitlines()[1:] == ["[TABELA]", "Imię | ", "Nazwisko | ", "[/TABELA]"]

def test_gdpr_clause_excluded_until_next_heading() -> None:
    doc = _doc([_p("Wnoszę o…"), _p("KLAUZULA INFORMACYJNA numeracja"), _p("Administratorem…"),
                _h("Oświadczenia"), _p("Oświadczam, że…")])
    text = doc.to_prompt_text()
    assert "Administratorem" not in text and "Oświadczam" in text
    assert "Administratorem" in doc.to_prompt_text(exclude_boilerplate=False)

def test_wniosek1_fixture_prompt_is_compact() -> None:
    doc = DocumentModel.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    text = doc.to_prompt_text()
    assert "Wójt Gminy Elbląg" in text and "w obrębie [POLE]" in text
    assert "Inspektora Ochrony Danych" not in text
    assert len(text) < 1200   # pełny tekst z RODO ma ok. 3300 znaków

def test_duplicate_block_ids_rejected() -> None: ...
def test_ocr_mean_confidence() -> None:  # [0.5, None, 0.9] → 0.7; brak OCR → None
```

- [ ] **Step 3: Run tests to verify they fail** – `uv run pytest tests/unit/test_document.py -v` → FAIL.

- [ ] **Step 4: Implement `document.py`** według reguł powyżej.

- [ ] **Step 5: Run tests** – `uv run pytest tests/unit/test_document.py -v && uv run mypy app && uv run ruff check app tests` → PASS. Jeśli `test_wniosek1_fixture_prompt_is_compact` nie mieści się w 1200 znakach, wypisz tekst i sprawdź, czy wycinanie RODO działa, zanim zmienisz próg.

- [ ] **Step 6: Commit**

```bash
git add app/models/document.py tests/unit/test_document.py tests/fixtures/documents/wniosek1.json
git commit -m "feat(models): DocumentModel with compact prompt rendering"
```

---

### Task 4: Konfiguracja trybów i timeoutów

**Files:**
- Modify: `backend/app/core/config.py` (sekcja `# --- LLM ---`)
- Modify: `.env.example`, `docs/specyfikacja-techniczna.md` (§6.1, §12, §13.2), `Makefile` (cel `model`), `docker-compose.yml` (obraz `llm`)
- Test: `backend/tests/unit/test_config_llm.py`

**Interfaces:**
- Produces: `LlmMode = Literal["accurate", "fast"]` (w `config.py`); pola `llm_fast_model: str = "qwen3:4b"`, `llm_default_mode: LlmMode = "accurate"`; zmienione domyślne `llm_timeout_s = 240`, `request_timeout_s = 540`; metoda `Settings.llm_model_for(mode: LlmMode) -> str` (`accurate` → `llm_model`, `fast` → `llm_fast_model`).

- [ ] **Step 1: Write the failing tests**

```python
def _settings(**kw: Any) -> Settings: return Settings(app_env="development", auth_enabled=False, **kw)

def test_llm_defaults() -> None:
    s = _settings()
    assert (s.llm_timeout_s, s.request_timeout_s, s.llm_default_mode) == (240, 540, "accurate")
    assert s.llm_model_for("accurate") == "qwen3:8b" and s.llm_model_for("fast") == "qwen3:4b"

def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValidationError): _settings(llm_default_mode="turbo")
```

- [ ] **Step 2: Run** – `uv run pytest tests/unit/test_config_llm.py -v` → FAIL.
- [ ] **Step 3: Implement** w `config.py`.
- [ ] **Step 4: Zaktualizuj otoczenie**
  - `.env.example`: `LLM_TIMEOUT_S=240`, dopisz `LLM_FAST_MODEL=qwen3:4b`, `LLM_DEFAULT_MODE=accurate`; `REQUEST_TIMEOUT_S=540` (jeśli zmienna jest w pliku – dopisz w sekcji limitów).
  - spec §12: wiersze `LLM_FAST_MODEL`, `LLM_DEFAULT_MODE`, nowe domyślne timeouty. §6.1: `POST /forms/convert?mode=accurate|fast` (domyślnie `LLM_DEFAULT_MODE`). §13.2: wiersz czasu CPU zastąp dwoma: `fast` p50 ≤ 70 s, p95 ≤ 150 s; `accurate` p50 ≤ 120 s, p95 ≤ 300 s.
  - `Makefile` `model`: drugi `ollama pull $${LLM_FAST_MODEL:-qwen3:4b}` w tym samym stylu co istniejący.
  - `docker-compose.yml`: `image: ollama/ollama:0.40.16` (usuń TODO o wersji, zostaw uwagę o digeście dla wydania).
- [ ] **Step 5: Run** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS (cały zestaw).
- [ ] **Step 6: Commit**

```bash
git add app/core/config.py tests/unit/test_config_llm.py ../.env.example ../docs/specyfikacja-techniczna.md ../Makefile ../docker-compose.yml
git commit -m "feat(config): accurate/fast LLM modes and CPU-realistic timeouts"
```

---

### Task 5: Klient Ollamy

**Files:**
- Create: `backend/app/pipeline/llm_client.py`
- Modify: `backend/pyproject.toml` (`[tool.pytest.ini_options]`: `asyncio_mode = "auto"`)
- Test: `backend/tests/unit/test_llm_client.py`

**Interfaces:**
- Consumes: `Settings` (Task 4).
- Produces:
  - `ChatMessage = TypedDict("ChatMessage", {"role": Literal["system","user","assistant"], "content": str})`
  - `@dataclass(frozen=True) LlmReply(content: str, prompt_tokens: int, output_tokens: int, duration_ms: int)`
  - wyjątki `LlmError(Exception)`, `LlmTimeoutError(LlmError)`, `LlmUnavailableError(LlmError)`
  - `class LlmClient(Protocol)`: `async def chat(self, *, model: str, messages: list[ChatMessage], schema: dict[str, Any], timeout_s: float) -> LlmReply`; `async def list_models(self) -> set[str]`; `async def warm_up(self, model: str) -> None`; `async def aclose(self) -> None`
  - `class OllamaClient(LlmClient)`: `__init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None)`, jeden `httpx.AsyncClient(base_url=settings.llm_base_url)`.

Kontrakt HTTP:
- `chat` → `POST /api/chat`, body: `{"model", "messages", "format": schema, "stream": false, "think": false, "keep_alive": "30m", "options": {"temperature", "seed", "num_ctx"}}`, timeout `timeout_s`. Odpowiedź: `message.content`, `prompt_eval_count`, `eval_count` (brak klucza → 0); `duration_ms` mierzone `time.perf_counter`.
- `list_models` → `GET /api/tags`, timeout 3 s, zwraca zbiór `models[].name`.
- `warm_up` → `POST /api/chat` z `{"model", "messages": [], "keep_alive": "30m"}`.
- Mapowanie błędów: `httpx.TimeoutException` → `LlmTimeoutError`; `httpx.TransportError` (inne), HTTP 5xx i HTTP 404 → `LlmUnavailableError`; niepoprawny JSON koperty odpowiedzi → `LlmUnavailableError`.

- [ ] **Step 1: Write the failing tests** – z `httpx.MockTransport`:

```python
async def test_chat_sends_contract_body() -> None:  # body zawiera think=False, stream=False, format==schema, options z Settings
async def test_chat_parses_reply() -> None:         # content + prompt_eval_count=1592, eval_count=546 → LlmReply
async def test_timeout_raises_llm_timeout() -> None:  # handler rzuca httpx.ReadTimeout
async def test_missing_model_raises_unavailable() -> None:  # 404 {"error":"model 'qwen3:4b' not found"}
async def test_server_error_raises_unavailable() -> None:   # 500
async def test_connection_error_raises_unavailable() -> None:  # httpx.ConnectError
async def test_list_models() -> None:  # {"models":[{"name":"qwen3:8b"},{"name":"qwen3:4b"}]} → {"qwen3:8b","qwen3:4b"}
```

- [ ] **Step 2: Run** – `uv run pytest tests/unit/test_llm_client.py -v` → FAIL.
- [ ] **Step 3: Implement `llm_client.py`.**
- [ ] **Step 4: Run** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS.
- [ ] **Step 5: Commit**

```bash
git add app/pipeline/llm_client.py tests/unit/test_llm_client.py pyproject.toml
git commit -m "feat(pipeline): Ollama client behind LlmClient protocol"
```

---

### Task 6: `analyze()` – wywołanie, ponowna próba, budżet, fallback

**Files:**
- Modify: `backend/app/pipeline/analyze.py`
- Create: `backend/app/resources/prompts/system.md`
- Create: `backend/tests/fixtures/llm_responses/wniosek1_valid.json`, `wniosek1_invalid_ref.json`
- Create: `backend/tests/unit/fakes.py` (`FakeLlmClient`)
- Test: `backend/tests/unit/test_analyze.py`

**Interfaces:**
- Consumes: `FormDraft`, `llm_schema` (Task 1), `ConversionWarning` (Task 1), `DocumentModel` (Task 3), `Settings`, `LlmMode` (Task 4), `LlmClient`, `ChatMessage`, `LlmReply`, `LlmTimeoutError`, `LlmUnavailableError` (Task 5).
- Produces:
  - `FallbackReason = Literal["timeout", "unavailable", "invalid_output", "empty_document"]`
  - `@dataclass AnalysisResult(draft: FormDraft | None, mode: LlmMode, model: str, duration_ms: int, retries: int, fallback: bool, fallback_reason: FallbackReason | None, prompt_tokens: int, output_tokens: int, warnings: list[ConversionWarning])`
  - `async def analyze(doc: DocumentModel, settings: Settings, client: LlmClient, *, deadline: float, mode: LlmMode | None = None, clock: Callable[[], float] = time.monotonic) -> AnalysisResult`
  - `load_system_prompt() -> str` (`@cache`, czyta `app/resources/prompts/system.md` przez `importlib.resources`)
  - Stałe: `MIN_CALL_BUDGET_S = 30`, `RETRY_BUDGET_FACTOR = 1.2`.
  - Hak do Task 7/8: `analyze` woła `normalize_draft(draft, doc)` i `split`/`merge` – w tym tasku jeszcze ich nie ma; normalizacja = tożsamość, brak fragmentacji.
- `FakeClock` (`now: float = 0.0`, `__call__() -> float`) i `FakeLlmClient(replies: list[LlmReply | Exception], clock: FakeClock, models: set[str] = {"qwen3:8b", "qwen3:4b"})`: zwraca/rzuca kolejne pozycje, przy każdym `chat` przesuwa `clock.now` o `reply.duration_ms / 1000`, zapisuje `calls: list[dict[str, Any]]` (`model`, `messages`, `timeout_s`). W testach `analyze(..., clock=clock)`, start zegara = 0, więc `deadline=1000` to 1000 s budżetu.

Przebieg (spec §5.4, §5.7):
1. `mode = mode or settings.llm_default_mode`; `model = settings.llm_model_for(mode)`.
2. `text = doc.to_prompt_text()`; pusty po `strip()` → fallback `empty_document` bez wywołania.
3. `remaining = deadline - clock()`; `< MIN_CALL_BUDGET_S` → fallback `timeout` bez wywołania.
4. Wiadomości: `system` = `load_system_prompt()`, `user` = `"<dokument>\n" + text + "\n</dokument>"`; timeout = `min(settings.llm_timeout_s, remaining)`.
5. `FormDraft.model_validate_json(reply.content)`; `ValidationError` (w tym zły JSON) → jeśli `mode == "accurate"` i `deadline - clock() >= first_call_s * RETRY_BUDGET_FACTOR`: ponowna próba z dodanymi wiadomościami `assistant` (odpowiedź modelu) + `user`: `"Odpowiedź nie spełnia schematu. Popraw błędy i zwróć cały szkic ponownie:\n" + "\n".join(f"- {loc}: {msg}")`; w przeciwnym razie fallback `invalid_output`.
6. `LlmTimeoutError` → fallback `timeout`; `LlmUnavailableError` → fallback `unavailable`.
7. Każdy fallback: `draft=None`, `fallback=True`, ostrzeżenie `W01_LLM_FALLBACK` z przyczyną w `message`. `prompt_tokens`/`output_tokens`/`duration_ms` sumowane po wywołaniach.

- [ ] **Step 1: Napisz `system.md`** (ok. 25 linii, po polsku) – na bazie `RULES` z testu na brudno (spec §4.1) z poprawkami: brak `semantic`/`summary_info`/`addresses`; „pełny tytuł, zwykła pisownia (nie wielkimi literami)”; „`statements` tylko oświadczenia dosłownie z dokumentu, pusta lista gdy ich nie ma”; „sekcja grupuje powiązane pola – nie twórz sekcji z jednym polem, jeśli pola dotyczą tego samego”; „`[POLE]` oznacza miejsce do wpisania danych”; kiedy `long_text`/`number`/`date`/`file`/`info`; „pola mają id f1, f2, … a `visible_when.field_id` wskazuje id pola wyboru”; „pole wyboru zawsze z opcjami”.

- [ ] **Step 2: Fixtures odpowiedzi** – `wniosek1_valid.json`: koperta Ollamy `{"message":{"content": "<JSON szkicu jak `_draft()` z Task 1 bez f5/f6>"}, "prompt_eval_count": 700, "eval_count": 300}`; `wniosek1_invalid_ref.json`: ten sam szkic z `visible_when` na `f9`.

- [ ] **Step 3: Write the failing tests** (`tests/unit/test_analyze.py`)

```python
async def test_valid_reply_returns_draft() -> None:
    r = await analyze(DOC, SETTINGS, fake(valid), deadline=1000)
    assert r.draft and r.draft.authority_name == "Wójt Gminy Elbląg"
    assert (r.fallback, r.retries, r.mode, r.model) == (False, 0, "accurate", "qwen3:8b")

async def test_request_contains_document_and_schema() -> None:  # calls[0]: system == load_system_prompt(), user zaczyna się od "<dokument>"
async def test_invalid_then_valid_retries_once() -> None:
    r = ...; assert r.retries == 1 and r.draft is not None
    assert "f9" in client.calls[1]["messages"][-1]["content"]          # błędy wróciły do modelu
    assert client.calls[1]["messages"][-2]["role"] == "assistant"
async def test_invalid_twice_falls_back() -> None:     # reason "invalid_output", warnings[0].code == "W01_LLM_FALLBACK"
async def test_truncated_json_is_invalid_output() -> None:  # content='{"title": "Wniosek o' (dwa razy)
async def test_fast_mode_never_retries() -> None:      # mode="fast": 1 wywołanie, model "qwen3:4b", fallback invalid_output
async def test_no_retry_when_budget_too_small() -> None:  # pierwsze wywołanie 100 s, deadline = start+150 → brak 2. wywołania
async def test_timeout_is_capped_by_deadline() -> None:   # deadline = start+90 → calls[0]["timeout_s"] == 90
async def test_exhausted_deadline_skips_llm() -> None:    # deadline = start+10 → 0 wywołań, reason "timeout"
async def test_empty_document_falls_back() -> None:       # tylko klauzula RODO → 0 wywołań, reason "empty_document"
async def test_timeout_falls_back() -> None:              # LlmTimeoutError → reason "timeout"
async def test_unavailable_falls_back() -> None:          # LlmUnavailableError → reason "unavailable"
async def test_default_mode_from_settings() -> None:      # llm_default_mode="fast", mode=None → model "qwen3:4b"
```

- [ ] **Step 4: Run** – `uv run pytest tests/unit/test_analyze.py -v` → FAIL.
- [ ] **Step 5: Implement `analyze.py`.** Logowanie (`logging`) czasu, tokenów, trybu i przyczyny fallbacku na INFO; bez treści dokumentu w logach.
- [ ] **Step 6: Run** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS.
- [ ] **Step 7: Commit**

```bash
git add app/pipeline/analyze.py app/resources/prompts/system.md tests/unit/test_analyze.py tests/unit/fakes.py tests/fixtures/llm_responses/
git commit -m "feat(pipeline): LLM analysis with retry, deadline and fallback"
```

---

### Task 7: Normalizacja szkicu

**Files:**
- Create: `backend/app/pipeline/draft_normalize.py`
- Modify: `backend/app/pipeline/analyze.py` (wywołanie po poprawnej walidacji)
- Test: `backend/tests/unit/test_draft_normalize.py`

**Interfaces:**
- Consumes: `FormDraft`, `DraftField`, `ConversionWarning` (Task 1), `DocumentModel` (Task 3).
- Produces: `normalize_draft(draft: FormDraft, doc: DocumentModel) -> tuple[FormDraft, list[ConversionWarning]]`, `matches_text(needle, haystack, threshold) -> bool`; wynik zawsze przechodzi `FormDraft.model_validate` (zbuduj go przez walidację słownika, nie `model_copy`).

Reguły, w tej kolejności (kody ostrzeżeń ustalone tu, spec §7 zostawia je wykonawcy):
1. `W15_CHOICE_WITHOUT_OPTIONS`: `single_choice` z < 2 opcjami albo `multi_choice` z 0 opcjami → `short_text`, `options=[]`; wszystkie `Condition` wskazujące to pole usunięte (to samo ostrzeżenie, `path` pola z warunkiem).
2. `W17_STATEMENT_REMOVED`: oświadczenie zawierające `[.…_]{3,}` albo niedopasowane do tekstu dokumentu → usunięte.
3. `W16_TITLE_CASE_NORMALIZED`: tytuł z ≥ 80% wielkich liter (spośród liter) → `t[0].upper() + t[1:].lower()`, potem słowa z `{"NIP","PESEL","REGON","KRS","RODO","CEIDG","VAT"}` przywrócone wielkimi.
4. `W13_FIELD_NOT_IN_DOCUMENT`: etykieta pola niedopasowana do tekstu dokumentu → tylko ostrzeżenie.
5. `W18_EMPTY_CONTAINER_REMOVED`: sekcje bez pól i strony bez sekcji usunięte (po krokach 1–4 nie powinny powstać, ale model może je zwrócić tylko jako strony bez sekcji).

Dopasowanie (publiczne `matches_text(needle: str, haystack: str, threshold: float) -> bool`, używane też w Task 10): oba teksty `casefold()`, `[POLE]` i znaki wypełnienia usunięte, białe znaki zwinięte; `SequenceMatcher(None, needle, haystack, autojunk=False).find_longest_match(...)`, trafienie gdy `match.size / len(needle) >= threshold`. Progi: **oświadczenia 0,8**, **etykiety 0,6**. Tekst dokumentu: `doc.to_prompt_text(exclude_boilerplate=True)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_condition_on_downgraded_choice_is_dropped() -> None:  # f5 single_choice bez opcji, f6 visible_when f5
    d, w = normalize_draft(draft, DOC)
    f5, f6 = _field(d, "f5"), _field(d, "f6")
    assert f5.kind == "short_text" and f6.visible_when == []
    assert {x.code for x in w} == {"W15_CHOICE_WITHOUT_OPTIONS"}
def test_single_checkbox_kept() -> None:            # multi_choice z 1 opcją zostaje
def test_statement_with_fill_dots_removed() -> None:  # "Budynek zlokalizowany w miejscowości……… przy ulicy……" (dosłownie z fixture 4b)
def test_statement_not_in_document_removed() -> None: # "Oświadczam, że dane są prawdziwe" przy dokumencie Wniosku 1
def test_statement_from_document_kept() -> None:      # dokument z akapitem "Oświadczam, że jestem właścicielem działki." → zostaje
def test_uppercase_title_normalized() -> None:
    assert _title("WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO") == "Wniosek o ustalenie numeru porządkowego"
    assert _title("WNIOSEK O NADANIE NUMERU NIP") == "Wniosek o nadanie numeru NIP"
    assert _title("Wniosek o wydanie zaświadczenia") == "Wniosek o wydanie zaświadczenia"  # bez ostrzeżenia
def test_labels_matched_against_document() -> None:  # fixture wniosek1: "Obręb", "Numer ewidencyjny działki" → brak W13; "Powierzchnia działki" → W13
def test_page_without_sections_removed() -> None:
def test_valid_draft_unchanged() -> None:  # szkic z wniosek1_valid.json → bez zmian, bez ostrzeżeń
```

Dodatkowo w `test_analyze.py`: `test_normalization_warnings_in_result` (odpowiedź z tytułem wielkimi literami → `W16` w `result.warnings`).

- [ ] **Step 2: Run** – `uv run pytest tests/unit/test_draft_normalize.py -v` → FAIL.
- [ ] **Step 3: Implement** `draft_normalize.py` i podepnij w `analyze.py`.
- [ ] **Step 4: Run** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS.
- [ ] **Step 5: Commit**

```bash
git add app/pipeline/draft_normalize.py app/pipeline/analyze.py tests/unit/test_draft_normalize.py tests/unit/test_analyze.py
git commit -m "feat(pipeline): normalize LLM drafts with conversion warnings"
```

---

### Task 8: Długie dokumenty – fragmenty i łączenie

**Files:**
- Create: `backend/app/pipeline/draft_merge.py`
- Modify: `backend/app/pipeline/analyze.py`
- Test: `backend/tests/unit/test_draft_merge.py`, uzupełnienie `tests/unit/test_analyze.py`

**Interfaces:**
- Consumes: `FormDraft` (Task 1), `analyze` (Task 6/7).
- Produces: `split_prompt_text(text: str, max_chars: int) -> list[str]`, `merge_drafts(drafts: list[FormDraft]) -> FormDraft`; stałe w `analyze.py`: `CHARS_PER_TOKEN = 3`, `RESPONSE_RESERVE_TOKENS = 2048`; `max_chars = (settings.llm_num_ctx - RESPONSE_RESERVE_TOKENS) * CHARS_PER_TOKEN - len(system_prompt)`.

Reguły:
- `split_prompt_text`: tnie na granicach linii `=== strona N`, sklejając kolejne strony, dopóki fragment ≤ `max_chars`; strona dłuższa niż `max_chars` cięta na granicach linii; linia dłuższa niż limit cięta twardo. Każdy fragment ≤ `max_chars`, kolejność zachowana, `"".join` po zdjęciu separatorów odtwarza treść.
- `merge_drafts`: metadane (`title`, `authority_*`, `applicant_kinds`) z pierwszego; `attachments`/`statements` – suma bez powtórzeń (kolejność pierwszego wystąpienia); strony o tej samej znormalizowanej nazwie (`casefold`, zwinięte spacje) łączone (sekcje doklejane); pole, którego znormalizowana etykieta już wystąpiła, pomijane; wszystkie pola przenumerowane `f1…fn` w kolejności, `visible_when` przepisane w obrębie fragmentu (warunek na pominięty duplikat → id zachowanego pola z tą etykietą); wynik przez `FormDraft.model_validate`.
- W `analyze`: jeden fragment = dotychczasowe zachowanie. Kilka fragmentów: kolejno, każdy z budżetem jak w Task 6, **bez ponownej próby**; nieudany fragment → `W14_PARTIAL_ANALYSIS` (`path` = `"chunk[i]"`) i dalej; brak budżetu na kolejny fragment → `W14` i koniec pętli; nieudany **pierwszy** fragment → fallback z przyczyną błędu. `retries` = 0.

- [ ] **Step 1: Write the failing tests**

```python
def test_short_text_single_chunk() -> None: assert split_prompt_text(T3, 10_000) == [T3]
def test_split_on_page_boundaries() -> None:  # 3 strony po 400 znaków, limit 900 → 2 fragmenty, granica przed "=== strona 3"
def test_oversized_page_split_on_lines() -> None:  # każdy fragment ≤ limit
def test_merge_renumbers_and_remaps_conditions() -> None:  # 2 szkice po f1,f2 (f2 visible_when f1) → f1..f4, f4 wskazuje f3
def test_merge_dedupes_by_label() -> None:  # "Miejscowość" w obu → raz
def test_merge_joins_same_titled_pages() -> None:
```
W `test_analyze.py`:
```python
async def test_long_document_chunked() -> None:       # llm_num_ctx=4096 w Settings (limit ≈ 6144 − len(system.md) znaków), dokument 3 strony po ok. 2500 znaków → ≥ 2 wywołania, szkice połączone
async def test_failed_later_chunk_gives_partial() -> None:  # 2. fragment niepoprawny → draft z 1., W14, fallback False
async def test_failed_first_chunk_falls_back() -> None:
```

- [ ] **Step 2: Run** – FAIL. **Step 3: Implement.** **Step 4: Run** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS.
- [ ] **Step 5: Commit**

```bash
git add app/pipeline/draft_merge.py app/pipeline/analyze.py tests/unit/test_draft_merge.py tests/unit/test_analyze.py
git commit -m "feat(pipeline): chunk long documents and merge partial drafts"
```

---

### Task 9: Podpięcie w aplikacji – klient, rozgrzewanie, `/health/ready`, `mode`

**Files:**
- Modify: `backend/app/main.py`, `backend/app/api/v1/health.py`, `backend/app/api/v1/forms.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: `OllamaClient`, `LlmClient`, `LlmUnavailableError` (Task 5), `Settings.llm_model_for`, `LlmMode` (Task 4), `AppError`, `ErrorCode.LLM_UNAVAILABLE` (istniejące `core/errors.py`).
- Produces: `create_app(settings: Settings | None = None, llm_client: LlmClient | None = None) -> FastAPI`; `app.state.llm_client`; zależność `get_llm_client(request: Request) -> LlmClient` w `llm_client.py`; `GET /health/ready` → `200 {"status": "ok"}` albo `200 {"status": "ok", "degraded": ["fast"]}` albo `503` problem+json `LLM_UNAVAILABLE`.
- `forms.convert`: dodany parametr `mode: LlmMode | None = None` (ciało dalej `NotImplementedError` – orkiestrator poza zakresem).

Lifespan (`asynccontextmanager`): jeśli `llm_client` nie podano – `OllamaClient(settings)`; przy starcie `asyncio.create_task(_warm_up(...))` dla `settings.llm_model_for(settings.llm_default_mode)` (wyjątek tylko logowany na WARNING, referencja do zadania trzymana w `app.state`, żeby nie zginęło); przy zamknięciu `aclose()`.

`/health/ready`: `list_models()`; `LlmUnavailableError`/`LlmTimeoutError` albo brak modelu trybu domyślnego → `AppError(ErrorCode.LLM_UNAVAILABLE)`; brak modelu drugiego trybu → `degraded` z nazwą tego trybu.

- [ ] **Step 1: Write the failing tests** (fałszywy klient z `tests/unit/fakes.py`)

```python
def test_ready_ok() -> None:            # models {"qwen3:8b","qwen3:4b"} → 200 {"status":"ok"}
def test_ready_degraded() -> None:      # {"qwen3:8b"} → 200, body["degraded"] == ["fast"]
def test_ready_default_model_missing() -> None:  # {"qwen3:4b"} → 503, code == "LLM_UNAVAILABLE", content-type problem+json
def test_ready_llm_down() -> None:      # list_models rzuca LlmUnavailableError → 503
def test_convert_accepts_mode_param() -> None:  # openapi: parametr "mode" z enum ["accurate","fast"] w /api/v1/forms/convert
```
Testy używają `with TestClient(create_app(settings, llm_client=fake)) as c:` (lifespan działa). `FakeLlmClient.warm_up` nic nie robi.

- [ ] **Step 2: Run** – `uv run pytest tests/test_health.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS (w tym stary `test_live`).
- [ ] **Step 5: Commit**

```bash
git add app/main.py app/api/v1/health.py app/api/v1/forms.py app/pipeline/llm_client.py tests/test_health.py
git commit -m "feat(api): LLM readiness check, client lifecycle and mode param"
```

---

### Task 10: Test na żywym modelu i pomiar

**Files:**
- Create: `backend/tests/integration/__init__.py`, `backend/tests/integration/test_llm_live.py`
- Modify: `backend/pyproject.toml` (`markers = ["llm: wymaga działającej Ollamy"]`, `addopts = "-m 'not llm'"`)
- Modify: `docs/superpowers/specs/2026-11-21-llm-models-design.md` (§5.7: wiersz „zmierzony czas po odchudzeniu”)

**Interfaces:**
- Consumes: `analyze`, `OllamaClient`, `matches_text` (Task 7), fixture `tests/fixtures/documents/wniosek1.json`; `LLM_BASE_URL` ze środowiska (domyślnie dla testu `http://localhost:11434`).

- [ ] **Step 1: Write the test**

```python
@pytest.mark.llm
@pytest.mark.parametrize("mode", ["accurate", "fast"])
async def test_wniosek1_live(mode: LlmMode) -> None:
    r = await analyze(DOC, settings, OllamaClient(settings), deadline=time.monotonic() + 600, mode=mode)
    print(f"{mode}: {r.duration_ms} ms, in={r.prompt_tokens}, out={r.output_tokens}, warnings={[w.code for w in r.warnings]}")
    assert r.draft is not None and not r.fallback
    labels = [f.label for _, f in r.draft.iter_fields()]
    found = sum(any(matches_text(e, l, 0.6) for l in labels) for e in ["Miejscowość", "Ulica", "Numer ewidencyjny działki", "Obręb"])
    assert found >= 3
    assert r.draft.authority_kind == "ORGAN"
```

- [ ] **Step 2: Run on the live model**

Run: `LLM_BASE_URL=http://localhost:11434 uv run pytest -m llm -s -v tests/integration`
Expected: 2 × PASS. Zanotuj czasy i tokeny z wydruku. Cele ze spec §5.7: `accurate` ≤ 120 s, `fast` ≤ 70 s. Jeśli cel nie jest spełniony – nie zmieniaj progów w teście, tylko zapisz wynik.

- [ ] **Step 3: Zapisz pomiar** w spec §5.7 (nowy wiersz tabeli „zmierzony czas po odchudzeniu, Wniosek 1”: wartości z kroku 2, tokeny wyjścia).

- [ ] **Step 4: Run the default suite** – `uv run pytest && uv run mypy app && uv run ruff check app tests` → PASS, test `llm` odznaczony jako deselected.

- [ ] **Step 5: Commit**

```bash
git add tests/integration pyproject.toml ../docs/superpowers/specs/2026-11-21-llm-models-design.md
git commit -m "test(llm): live Ollama check with timing for both modes"
```
