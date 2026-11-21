# Specyfikacja techniczna – „Cyfryzacja formularzy” (HackNation 2026, zadanie COI)

| | |
|---|---|
| Wersja | 0.1 (robocza) |
| Data | 2026-11-21 |
| Stack | Angular · REST API · Python 3.14+ · FastAPI · Docker |
| Źródła | pliki w `` (treść zadania, regulamin, standardy projektowania, reguły techniczne JSON, słowniki, dane inicjalne, wzorcowe JSON-y) |

---

## 1. Cel i zakres

System przyjmuje blankiet formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG), analizuje go lokalnym modelem AI i zwraca JSON z konfiguracją formularza elektronicznego, gotową do importu w Generatorze Formularzy COI.

Użytkownik docelowy: urzędnik, który przenosi papierowe formularze do e-usług.

### 1.1. Zakres obowiązkowy (pkt 3.2 zadania)

| ID | Wymaganie | Gdzie w specyfikacji |
|---|---|---|
| M1 | REST API przyjmujące pojedynczy plik w 8 formatach i zwracające JSON | §5, §6 |
| M2 | JSON zgodny ze strukturą wzorcową (`konfiguracja_form_*.json`, `importowanyPlikJsonSchemat`) | §7 |
| M3 | JSON zgodny ze standardami projektowania (strony tematyczne, sekcje predefiniowane itd.) | §7.3, §8 |
| M4 | Walidacja pliku: rozszerzenie + MIME, nazwa ≤ 250 znaków bez `; : > < / \ \| ' * % $`, konfigurowalny limit rozmiaru | §6.3 |
| M5 | Pliki przetwarzane tylko w pamięci lub katalogu tymczasowym na czas żądania | §10.3 |
| M6 | Docker zgodny z wymaganiami dla obrazów | §11 |
| M7 | Konfiguracja: limit rozmiaru, JWT, parametry integracji | §12 |
| M8 | Dokumentacja architektury + README (build, uruchomienie, konfiguracja, API) | §4, §15 |

### 1.2. Rozszerzenia opcjonalne (pkt 3.3) – wszystkie planujemy

| ID | Rozszerzenie | Gdzie |
|---|---|---|
| O1 | Powiązanie pól ze słownikami i danymi inicjalnymi | §8.4, §8.5 |
| O2 | Propozycje nowych słowników | §8.6 |
| O3 | Zależności pól/sekcji/stron (JSONata `states`, `flow`) | §8.7 |
| O4 | Frontend: upload plików i podgląd JSON | §9 |
| O5 | Wizualizacja formularza e-usługi na podstawie JSON | §9.3 |
| O6 | Walidacje pól (PESEL, NIP, REGON, kod pocztowy, e-mail…), batch, makiety | §8.3, §9 |

### 1.3. Poza zakresem

- Trwałe przechowywanie plików i wyników (wymóg M5 tego zabrania).
- Edytor JSON z zapisem zmian (frontend pokazuje i pozwala pobrać wynik).
- Wizualizacja dokumentu na podstawie CRWDE (standardy wprost wyłączają ją z zadania).
- Zarządzanie użytkownikami. Jest jedno konto techniczne z konfiguracji (§10.1).

---

## 2. Ograniczenia z treści zadania

Te ograniczenia determinują wybór technologii:

1. **Żadnych zewnętrznych API, SaaS ani MCP w działaniu rozwiązania.** Modeli LLM dostępnych tylko przez API nie wolno używać. Model musi działać lokalnie, w kontenerze.
2. **Tylko open source bez copyleftu.** GPL i AGPL są zakazane. Odpada m.in. **PyMuPDF (AGPL)**, `Unidecode` (GPL) i `antiword` (GPL).
3. **Bez licencji komercyjnych.**
4. **Najnowsze stabilne wersje bibliotek.**
5. **Python 3.14+.**
6. **Ocena na żywo:** finaliści uruchamiają rozwiązanie na nowych, nieznanych plikach. Liczy się więc ogólność i powtarzalność, a nie dopasowanie do przykładów.
7. **Kryteria oceny:** kompletność 30%, intuicyjność 20%, oryginalność 10%, jakość kodu 20%, potencjał wdrożeniowy z kosztem 20%. Dlatego wybieramy mały model działający na CPU (§3.3).

---

## 3. Stack technologiczny

### 3.1. Backend (Python 3.14, FastAPI)

| Obszar | Biblioteka | Licencja | Uwagi |
|---|---|---|---|
| Framework HTTP | FastAPI, Starlette | MIT / BSD-3 | OpenAPI generowane automatycznie |
| Serwer ASGI | Uvicorn | BSD-3 | |
| Modele i konfiguracja | Pydantic v2, pydantic-settings | MIT | schematy wejścia/wyjścia i schemat odpowiedzi LLM |
| Upload | python-multipart | Apache-2.0 | |
| JWT | PyJWT | MIT | |
| Wykrywanie MIME | python-magic + libmagic | MIT / BSD | sygnatura binarna pliku |
| PDF – tekst i współrzędne | pdfplumber (pdfminer.six) | MIT | **nie PyMuPDF (AGPL)** |
| PDF – rasteryzacja do OCR | pypdfium2 | Apache-2.0 / BSD-3 | |
| DOCX | python-docx | MIT | |
| XLSX | openpyxl | MIT | scalone komórki, obramowania |
| DOC → DOCX, ODS → XLSX | LibreOffice headless (proces zewnętrzny) | MPL-2.0 | patrz §3.4 |
| Obrazy | Pillow | MIT-CMU | preprocessing, limit pikseli |
| OCR | Tesseract 5 + `pol` (przez pytesseract) | Apache-2.0 | |
| Bezpieczne XML | defusedxml | PSF | ochrona przed XXE i bombami XML |
| Klient LLM | httpx | BSD-3 | wywołania lokalnego serwera modelu |
| JSON Schema | jsonschema | MIT | walidacja wyniku |
| JSONata | jsonata-python | Apache-2.0 (do weryfikacji) | kompilacja i test wygenerowanych warunków |
| Narzędzia | uv, ruff, mypy, pytest, pip-licenses | MIT/Apache | |

Transliterację do `techName` (ą→a, ł→l…) robimy w bibliotece standardowej (`unicodedata` + mapa dla `ł/Ł`), żeby nie wciągać `Unidecode` (GPL).

### 3.2. Frontend (Angular)

| Obszar | Wybór | Licencja |
|---|---|---|
| Framework | Angular, najnowsza stabilna (≥ 21): komponenty standalone, signals, nowy control flow | MIT |
| Stan aplikacji | NgRx Store + Effects + Entity (+ Store DevTools w trybie dev) | MIT |
| Style | Tailwind CSS (konfiguracja przez `@tailwindcss/postcss`, tokeny kolorów i typografii w jednym pliku motywu) | MIT |
| Prymitywy UI i dostępność | Angular CDK (a11y/focus trap, drag & drop, overlay); bez Angular Material | MIT |
| Ewaluacja warunków | `jsonata` (npm) | MIT |
| HTTP | `HttpClient` z interceptorem JWT | MIT |
| Testy | Vitest (jednostkowe), Playwright (e2e) | MIT / Apache-2.0 |
| Serwowanie | nginx (statyczne pliki + reverse proxy `/api`) | BSD-2 |

Stan globalny trzyma NgRx Store w trzech slice'ach: `auth` (token, wygaśnięcie), `importQueue` (EntityAdapter: plik, status, błąd, wynik, raport) i `catalog` (słowniki, źródła danych inicjalnych). Wywołania API i kolejkę batch obsługują Effects: `mergeMap` z limitem `BATCH_CONCURRENCY`, ponowienie i anulowanie. Komponenty czytają stan przez `store.selectSignal()`. Odpowiedzi wpisywane w podglądzie formularza są stanem lokalnym komponentu renderera (signals). Nie trafiają do Store, bo zmieniają się przy każdym naciśnięciu klawisza i nie są współdzielone.

Tailwind odpowiada za layout i wygląd: siatkę formularza `grid-cols-3` z `grid-area` z JSON, stany fokusu i błędów oraz tryb wysokiego kontrastu. Komponenty pól są własne, oparte na natywnych elementach HTML i CDK, dzięki czemu kontrolujemy dostępność (WCAG 2.1 AA).

### 3.3. Model AI (lokalnie)

| Element | Wybór | Licencja |
|---|---|---|
| Serwer inferencji | Ollama (alternatywnie llama.cpp `llama-server`) | MIT |
| Model domyślny | Qwen3 8B Instruct, kwantyzacja Q4_K_M (~5 GB RAM) | Apache-2.0 |
| Model alternatywny (język polski) | Bielik 11B v2 Instruct | Apache-2.0 (do weryfikacji) |
| Model wizyjny (opcja dla skanów) | Qwen2.5-VL 7B / Qwen3-VL | Apache-2.0 (do weryfikacji) |

Uzasadnienie:
- licencje Apache-2.0 spełniają wymóg braku copyleftu, a Llama i Gemma mają licencje niebędące OSI, więc je odrzucamy;
- model 7–11B w Q4 działa na CPU (8 rdzeni, 16 GB RAM), a GPU jest opcjonalne. To niski koszt wdrożenia;
- Ollama obsługuje *structured outputs*: przekazujemy JSON Schema z Pydantic i dostajemy poprawny składniowo JSON;
- model jest parametrem konfiguracji (`LLM_MODEL`), więc można go wymienić bez zmian w kodzie.

### 3.4. Licencje – zasady

- CI uruchamia `pip-licenses` i `license-checker` (npm). Build kończy się błędem, jeśli pojawi się GPL, AGPL, LGPL albo SSPL.
- **LibreOffice (MPL-2.0)** to copyleft słaby, na poziomie pliku. Obowiązek publikacji dotyczy tylko zmodyfikowanych plików MPL. Używamy niezmodyfikowanego binarium jako osobnego procesu, więc nasz kod nie podlega MPL. Do potwierdzenia z mentorami COI (§14, Q7). Plan B: przyjmujemy DOC/ODS tylko wtedy, gdy LibreOffice jest dostępny w obrazie, a w przeciwnym razie zwracamy 415.
- Obrazy bazowe Docker zawierają pakiety systemowe na różnych licencjach. To typowa sytuacja dla dystrybucji i nie wpływa na licencję naszego kodu.

---

## 4. Architektura

### 4.1. Kontenery

```
┌──────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────┐
│ frontend (nginx)     │      │ api (FastAPI, Python 3.14)│      │ llm (Ollama)          │
│ Angular SPA          │─────▶│ walidacja → normalizacja  │─────▶│ Qwen3 8B (Apache-2.0) │
│ :8080                │ /api │ → ekstrakcja → analiza AI │ HTTP │ :11434 tylko w sieci  │
│                      │      │ → budowa → weryfikacja    │      │ wewnętrznej           │
└──────────────────────┘      │ :8000                     │      └───────────────────────┘
                              │ tmpfs /tmp (pliki żądań)  │
                              └───────────────────────────┘
```

- **api** jest samodzielne i spełnia cały zakres obowiązkowy. Frontend jest opcjonalny.
- **llm** nie publikuje portu na hosta. Działa tylko w sieci `internal` Dockera.
- Nie ma bazy danych. Słowniki, katalog danych inicjalnych i szablony sekcji to pliki zasobów w obrazie `api`.

### 4.2. Moduły backendu

```
backend/
  app/
    main.py                  # FastAPI app, routery, middleware, handler błędów (RFC 9457)
    api/v1/
      auth.py                # POST /auth/token
      forms.py               # POST /forms/convert, POST /forms/validate
      catalog.py             # GET /dictionaries, GET /initial-data-sources
      health.py              # /health/live, /health/ready
    core/
      config.py              # Settings (pydantic-settings, zmienne środowiskowe)
      security.py            # wydawanie i weryfikacja JWT
      errors.py              # wyjątki domenowe → problem+json
    pipeline/
      upload_validation/     # nazwa, rozmiar, rozszerzenie, MIME, bomby ZIP
        receive.py           #   strumieniowy odbiór multipart (1 plik, limit, spool, hasło)
        filename.py          #   długość i znaki nazwy, rozszerzenie
        mime.py              #   MIME z zawartości (libmagic) vs rozszerzenie
        containers.py        #   DOCX/XLSX/ODS (ZIP, XML bez DTD), DOC (OLE)
        documents.py         #   PDF (strony), obrazy (piksele)
        encryption.py        #   pliki z hasłem: PDF, DOCX/XLSX/DOC (msoffcrypto), ODS
        odf_encryption.py    #   ODF: AES-CBC+PBKDF2, AES-GCM+Argon2id
        validate.py          #   kolejność sprawdzeń → ValidatedUpload
      pdfium_lock.py         # PDFium nie jest thread-safe: wspólna blokada
      normalize.py           # LibreOffice: DOC→DOCX, ODS→XLSX (timeout, sandbox)
      extract/               # pdf.py, docx.py, xlsx.py, image.py → DocumentModel
      analyze.py             # prompt + wywołanie LLM → FormDraft
      issues.py              # Issue + kody ostrzeżeń/błędów (W01…, R01…)
      build/                 # build_form / build_fallback → BuildResult
        ir.py                #   reprezentacja pośrednia: strony → sekcje → pola, warunki
        catalogs.py          #   ładowanie katalogów słowników, danych inicjalnych, schematu
        html.py              #   opisy HTML (escape tekstu ze szkicu, linki zewnętrzne)
        sections.py          #   sekcje predefiniowane (szablony) + BuildOptions
        fields.py            #   mapowanie typów, walidatory, techName
        dictionaries.py      #   powiązania słowników + propozycje nowych
        initial_data.py      #   PESEL / PESEL_ADDRESS / MLPZ
        states.py            #   generator i tester zapytań JSONata
        layout.py            #   x, y, rows, cols (questionOrder = y)
        pages.py             #   strony przedmiotu, rozwiązywanie warunków, flow.links
        serialize.py         #   IR → FormDefinition (kształt wzorców)
      verify.py              # JSON Schema + reguły R01–R15 + autonaprawa
    models/
      document.py            # DocumentModel (wynik ekstrakcji)
      draft.py               # FormDraft (wynik LLM, schemat structured output)
      form.py                # FormDefinition (wynik końcowy = format importu)
    resources/
      schema/importowanyPlikJsonSchemat.json
      templates/*.json       # sekcje predefiniowane wycięte z wzorcowych JSON-ów
      dictionaries.json      # katalog słowników (§8.4)
      initial_data.json      # katalog źródeł i atrybutów (§8.5)
      prompts/*.md           # prompty systemowe (reguły projektowania w skrócie)
  tests/
```

### 4.3. Zasada podziału pracy: AI rozumie, kod buduje

LLM odpowiada tylko za **semantykę**: jakie dane zbiera formularz, jak je pogrupować, jakie są warunki i kto może złożyć wniosek. Wszystko, co da się opisać regułą, robi **deterministyczny kod**: identyfikatory, `techName`, układ siatki, sekcje predefiniowane, walidatory, słowniki, dane inicjalne, składnia JSONata, `flow`.

Korzyści:
- mały model wystarcza, bo nie musi generować 100 KB JSON-a, tylko zwięzły szkic;
- wynik jest zawsze zgodny ze schematem i regułami, nawet gdy model się pomyli;
- powtarzalność: temperatura 0, stały seed i walidacja po każdym kroku;
- odporność na *prompt injection* w treści dokumentu: model zwraca dane w sztywnym schemacie, a kod nie wykonuje niczego, co model „poleci”.

---

## 5. Przepływ przetwarzania (pipeline)

```
plik ─▶ [1] walidacja ─▶ [2] normalizacja ─▶ [3] ekstrakcja ─▶ [4] analiza LLM
     ─▶ [5] budowa formularza ─▶ [6] weryfikacja i autonaprawa ─▶ JSON
```

### 5.1. [1] Walidacja wejścia
Szczegóły w §6.3. Błąd kończy żądanie przed jakimkolwiek parsowaniem.

### 5.2. [2] Normalizacja
- `.doc` → `.docx` i `.ods` → `.xlsx` przez `soffice --headless --convert-to`, w osobnym katalogu tymczasowym, z timeoutem (`CONVERTER_TIMEOUT_S`) i osobnym profilem użytkownika LibreOffice na każde żądanie.
- Pozostałe formaty przechodzą bez zmian.

### 5.3. [3] Ekstrakcja → `DocumentModel`
Wspólny model pośredni niezależny od formatu: lista stron, a na stronie lista bloków (`heading`, `paragraph`, `label`, `input_placeholder`, `checkbox_option`, `table`, `table_cell`) z tekstem, kolejnością, przybliżoną pozycją i flagą pewności OCR.

| Format | Metoda | Rozpoznawane wzorce pól |
|---|---|---|
| PDF z warstwą tekstu | pdfplumber: słowa ze współrzędnymi, linie, prostokąty, tabele | ciągi `....`/`____`, puste prostokąty (pola), małe kwadraty (checkboxy), pola AcroForm |
| PDF bez tekstu (skan) | pypdfium2 → PNG 300 DPI → OCR | jak dla obrazów |
| JPG/JPEG/PNG | Pillow (skala szarości, binaryzacja, korekta orientacji z Tesseract OSD) → Tesseract `pol` (TSV ze współrzędnymi) | jak wyżej + znaki `☐ □ ■ X` |
| DOCX | python-docx: akapity, style nagłówków, tabele, pola formularza | `☐`, podkreślenia, puste komórki tabel obok etykiet |
| XLSX | openpyxl: komórki, scalenia, obramowania | komórka z etykietą + pusta komórka z obramowaniem obok |

Tryb opcjonalny (`EXTRACTION_VLM_ENABLED=true`): strony skanów idą dodatkowo do modelu wizyjnego, który lepiej wykrywa zaznaczenia i układ. Domyślnie wyłączony ze względu na koszt.

### 5.4. [4] Analiza LLM → `FormDraft`
- Wejście: `DocumentModel` zserializowany do zwięzłego tekstu z markerami (`[POLE]`, `[OPCJA]`, `[TABELA]`) oraz prompt systemowy ze skrótem standardów (§8).
- Wyjście: JSON wymuszony schematem `FormDraft` (Pydantic → JSON Schema → parametr `format` w Ollama):

```jsonc
{
  "title": "Wniosek o stwierdzenie nadpłaty podatku",
  "authority": { "kind": "URZAD|ORGAN", "name": "Urząd Gminy …" },
  "applicantKinds": ["SELF", "OTHER_PERSON", "LEGAL_ENTITY"],   // kto może złożyć
  "addresses": ["ZAMIESZKANIA"],                                 // jakie adresy wnioskodawcy
  "subjectPages": [
    {
      "title": "Informacje o nadpłacie",
      "sections": [
        {
          "title": "Rozliczenie nadpłaty",
          "repeating": false,
          "fields": [
            {
              "label": "Wybierz, co mamy zrobić z nadpłatą",
              "kind": "single_choice|multi_choice|short_text|long_text|number|date|file|info",
              "required": true,
              "options": ["Zaliczyć na poczet przyszłego zobowiązania podatkowego",
                          "Zwrócić przelewem na rachunek bankowy"],
              "semantic": "BANK_ACCOUNT|PESEL|NIP|…|null",
              "visibleWhen": null
            },
            {
              "label": "Numer rachunku", "kind": "short_text", "required": true,
              "semantic": "BANK_ACCOUNT",
              "visibleWhen": { "field": "Wybierz, co mamy zrobić z nadpłatą",
                               "op": "equals", "value": "Zwrócić przelewem na rachunek bankowy" }
            }
          ]
        }
      ]
    }
  ],
  "attachments": ["Deklaracja podatkowa"],
  "statements": ["Oświadczam, że dane są zgodne z prawdą"],
  "summaryInfo": "Urząd rozpatrzy wniosek w ciągu 30 dni"
}
```

- Duże dokumenty dzielimy na fragmenty po stronach. Szkice łączymy w kodzie, deduplikując po etykiecie.
- Przy błędzie walidacji szkicu robimy jedną ponowną próbę z listą błędów w promptcie, potem degradację (§5.6).
- Parametry: `temperature=0`, stały `seed`, timeout `LLM_TIMEOUT_S`.

### 5.5. [5] Budowa formularza (deterministyczna)
Szczegółowe reguły w §8. Kolejność:
1. Tytuł (normalizacja, ≤ 255 znaków).
2. Strona 1 „Dane”: sekcje predefiniowane dobrane według `applicantKinds` i `addresses`.
3. Strony przedmiotu wniosku z `subjectPages`.
4. Przedostatnia strona: „Dane do kontaktu”, załączniki, które nie trafiły wyżej, oraz „Zgody i oświadczenia” (`CONSENT_SECTION`).
5. Strona końcowa `FINISH`: podsumowanie i podgląd.
6. Mapowanie typów, walidatorów, słowników i danych inicjalnych, generowanie `techName`, UUID, układu i `states`.
7. `flow.links` łączy strony po kolei.

### 5.6. [6] Weryfikacja i autonaprawa
- Walidacja JSON Schema (`importowanyPlikJsonSchemat.json`, z poprawkami z §7.4).
- Walidator reguł biznesowych (§7.3). Każde naruszenie ma kod, np. `R03_FIELD_OUTSIDE_SECTION`.
- Automatyczne naprawy: pusta strona → usunięcie; pole poza sekcją → opakowanie w sekcję; zduplikowany `techName` → sufiks `_2`; zapytanie JSONata, które się nie kompiluje albo wskazuje nieistniejące pole → usunięcie stanu i ostrzeżenie.
- Degradacja: jeśli LLM zawiedzie (timeout, niepoprawny JSON po ponownej próbie), budujemy formularz z samych sekcji predefiniowanych i heurystycznie wykrytych pól. Odpowiedź ma wtedy ostrzeżenie `W01_LLM_FALLBACK`. Użytkownik zawsze dostaje poprawny strukturalnie JSON.

---

## 6. REST API

Prefiks `/api/v1`. Dokumentacja OpenAPI pod `/docs` (Swagger UI) i `/openapi.json`. Wszystkie endpointy oprócz `/auth/token` i `/health/*` wymagają nagłówka `Authorization: Bearer <JWT>`.

### 6.1. Endpointy

| Metoda | Ścieżka | Opis | Odpowiedź |
|---|---|---|---|
| POST | `/auth/token` | logowanie kontem technicznym z konfiguracji (`application/x-www-form-urlencoded`: `username`, `password`) | `200 {access_token, token_type, expires_in}` |
| POST | `/forms/convert` | **główny endpoint**: `multipart/form-data`, pole `file` (dokładnie 1 plik) | `200 application/json` – konfiguracja formularza (§7) |
| POST | `/forms/convert?report=true` | jak wyżej, ale odpowiedź zawiera też raport | `200 {form, report}` |
| POST | `/forms/validate` | walidacja dowolnego JSON-a formularza (np. poprawionego ręcznie) | `200 {valid, errors[], warnings[]}` |
| GET | `/dictionaries` | katalog słowników: predefiniowane i proponowane | `200 [...]` |
| GET | `/initial-data-sources` | źródła danych inicjalnych i ich atrybuty | `200 [...]` |
| GET | `/health/live` | proces działa | `200` |
| GET | `/health/ready` | API gotowe, LLM osiągalny, model załadowany | `200` / `503` |

Domyślna odpowiedź `/forms/convert` to **czysty JSON w formacie importu**, bez opakowania, żeby dało się go bezpośrednio zaimportować. Raport jest opcjonalny (`report=true`). Ostrzeżenia sygnalizuje też nagłówek `X-Conversion-Warnings: <liczba>`.

### 6.2. Raport konwersji (`report`)

```json
{
  "sourceFile": { "name": "Wniosek o zwrot opłaty skarbowej.pdf", "mime": "application/pdf", "sizeBytes": 183211, "pages": 2, "decrypted": false },
  "extraction": { "method": "pdf_text|ocr|docx|xlsx", "convertedToOpenXml": false, "ocrMeanConfidence": null, "blocks": 87 },
  "llm": { "model": "qwen3:8b", "durationMs": 21430, "retries": 0, "fallback": false, "fallbackReason": null,
           "ruleBasedDraft": false, "promptTokens": 2192, "outputTokens": 318 },
  "stats": { "tabs": 4, "sections": 15, "fields": 62, "states": 27 },
  "dictionaryProposals": [ { "name": "RODZAJE_PODATKOW", "title": "…", "items": [ { "code": "…", "name": "…", "techName": "…" } ], "usedBy": ["nazwa_podatku"] } ],
  "warnings": [ { "code": "W12_LOW_OCR_CONFIDENCE", "message": "…", "path": "tabs[1].questions[0]" } ],
  "fixes": [ { "code": "R12_DUPLICATE_TECH_NAME", "message": "…", "path": "…" } ],
  "timings": { "normalizeMs": 0, "extractMs": 140, "analyzeMs": 21430, "buildMs": 310 },
  "durationMs": 25110
}
```

Implementacja: `pipeline/convert.py` (`convert_upload`) łączy etapy [2]–[6]; endpoint (`api/v1/forms.py`) odbiera plik strumieniowo, waliduje go ([1]), czeka na miejsce w `MAX_CONCURRENT_JOBS` i liczy `REQUEST_TIMEOUT_S` od wejścia żądania (czekanie na semafor też się wlicza; po terminie 504 `PROCESSING_TIMEOUT`). `fixes` to poprawki autonaprawy z kroku [6]. Gdy formularz po autonaprawie nadal ma błędy, zwracamy formularz zastępczy z ostrzeżeniem `W27_FORM_REBUILT`.

### 6.3. Walidacja pliku (wymóg M4)

Kolejność sprawdzeń. Pierwsze naruszenie kończy żądanie.

| # | Reguła | Błąd |
|---|---|---|
| 1 | Dokładnie jedno pole `file` w żądaniu | 400 `FILE_MISSING` / `TOO_MANY_FILES` |
| 2 | Nazwa pliku ≤ 250 znaków | 400 `FILENAME_TOO_LONG` |
| 3 | Nazwa nie zawiera `; : > < / \ \| ' * % $` | 400 `FILENAME_FORBIDDEN_CHARS` |
| 4 | Rozmiar ≤ `MAX_FILE_SIZE_MB`. Liczymy strumieniowo i przerywamy po przekroczeniu, bez buforowania całości. nginx ma ten sam limit (`client_max_body_size`) | 413 `FILE_TOO_LARGE` |
| 5 | Rozszerzenie (bez rozróżniania wielkości liter) ∈ {pdf, doc, docx, ods, xlsx, jpg, jpeg, png} | 415 `UNSUPPORTED_EXTENSION` |
| 6 | MIME z zawartości (libmagic) zgodny z rozszerzeniem według tabeli poniżej. Nagłówek `Content-Type` od klienta ignorujemy | 415 `MIME_MISMATCH` |
| 7 | Kontenery ZIP (docx, xlsx, ods): sprawdzamy oczekiwane wpisy (`[Content_Types].xml` + `word/` lub `xl/`; dla ODS wpis `mimetype` = `application/vnd.oasis.opendocument.spreadsheet`), sumę rozmiarów po dekompresji ≤ `MAX_UNCOMPRESSED_MB` i liczbę wpisów | 415 `MIME_MISMATCH` / 422 `ARCHIVE_TOO_LARGE` |
| 8 | Obrazy: liczba pikseli ≤ `MAX_IMAGE_PIXELS`. PDF: liczba stron ≤ `MAX_PDF_PAGES` | 422 `DOCUMENT_TOO_COMPLEX` |
| 9 | Plik da się otworzyć (nie jest uszkodzony ani zaszyfrowany) | 422 `DOCUMENT_UNREADABLE` |

| Rozszerzenie | Akceptowane MIME (z zawartości) |
|---|---|
| pdf | `application/pdf` |
| doc | `application/msword`, `application/x-ole-storage`, `application/CDFV2` |
| docx | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (lub `application/zip` + sprawdzenie struktury z pkt 7) |
| xlsx | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (lub `application/zip` + pkt 7) |
| ods | `application/vnd.oasis.opendocument.spreadsheet` (lub `application/zip` + pkt 7) |
| jpg, jpeg | `image/jpeg` |
| png | `image/png` |

Plik `.doc`, który w środku jest DOCX (Word potrafi tak zapisać; są takie w materiałach), traktujemy jak DOCX: przechodzi pełne sprawdzenie struktury z pkt 7 i omija konwersję.

W docs/ jest plik `.JPE` (w treści zadania nie ma takiego rozszerzenia). Odrzucamy go z 415, chyba że mentorzy zdecydują inaczej (§14, Q8).

### 6.4. Format błędów
RFC 9457 `application/problem+json`:

```json
{ "type": "https://coi-cf/errors/FILENAME_FORBIDDEN_CHARS", "title": "Niedozwolone znaki w nazwie pliku",
  "status": 400, "detail": "Nazwa pliku zawiera znak ':'", "code": "FILENAME_FORBIDDEN_CHARS" }
```

Pozostałe kody: 401 (brak lub niepoprawny token), 503 `LLM_UNAVAILABLE`, 504 `PROCESSING_TIMEOUT`, 500 (bez szczegółów wewnętrznych w treści, pełny log po stronie serwera z `request_id`).

### 6.5. Przykład

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token -d "username=$API_USER&password=$API_PASSWORD" | jq -r .access_token)
curl -s -X POST localhost:8000/api/v1/forms/convert -H "Authorization: Bearer $TOKEN" \
     -F "file=@docs/Wniosek o zwrot opłaty skarbowej.pdf" > wynik.json
```

---

## 7. Format wyjściowy JSON

### 7.1. Struktura
Zgodna z `OpisImportowanegoPlikuJSON` i wzorcami `konfiguracja_form_*.json`:

```
FormDefinition
├── title: string (≤255)
├── tabs[]: { id (UUID), title, type: "MAIN" | "FINISH", questions[] }
│     questions[] (poziom strony = tylko SECTION / REPEATING_SECTION)
│       { x, y, rows, cols, field: {
│           id (UUID), type, techName, title, description, tooltipMessage,
│           options[], validation[], readOnly, states[], questionOrder,
│           repeatingSectionGrid[]   ← pola sekcji (ta sama struktura question)
│           [defaultValue, defaultValueType, dictionaryName, searchEnabled,
│            multiLevelTree, consentSectionConfig, selectAllEnabled] } }
└── flow: { links[]: { id (UUID), source (tab.id), target (tab.id) } }
```

### 7.2. Konwencje (przyjęte z wzorcowych JSON-ów)
- Każdy obiekt `field` ma komplet kluczy bazowych (`id, type, techName, title, description, options, validation, readOnly, repeatingSectionGrid, states, questionOrder, tooltipMessage`), nawet puste. Tak wyglądają wzorce i to ułatwia import.
- `techName`: snake_case ASCII z etykiety (`Numer PESEL` → `numer_pesel`), unikalny w formularzu. Dla powtórzeń sekcji predefiniowanych dodajemy sufiks kontekstu, jak we wzorcu: `kraj_siedziba`, `wojewodztwo_inna_osoba`.
- `options[].id` = `options[].name` (tak jest we wzorcach). `techName` opcji to slug nazwy.
- Układ: jedna kolumna (standard pkt 2), `cols = 3`, `x = 0`. `y` rośnie kolejno w sekcji, `rows = 1` dla pól. Dla sekcji `rows` = suma wierszy pól + 1 na nagłówek, `y` sekcji to skumulowana wysokość. `questionOrder` = kolejność w kontenerze.
- `description` sekcji i bloków tekstu to HTML (`<html><head></head><body>…</body></html>`). Linki zewnętrzne mają `target="_blank" rel="noopener noreferrer" aria-label="Link otwiera się w nowej karcie"`. Wzorce zawierają obrazy ikon w base64; my je pomijamy, ikonę dodaje renderer.
- `defaultValue` dla `SELECT` jest tablicą (`["Polska"]`), dla pól tekstowych stringiem (zgodnie z wzorcem; schemat mówi tylko o stringu, §7.4).
- Walidacja obowiązkowości: pole wymagane ma `"REQUIRED"` w `validation`, a pole opcjonalne nie ma (§14, Q2).

### 7.3. Reguły strukturalne (weryfikowane w kroku [6])

| Kod | Reguła (źródło: „Reguły techniczne…”) |
|---|---|
| R01 | `title` niepusty, ≤ 255 znaków, zaczyna się od „Wniosek”, „Zgłoszenie”, „Deklaracja” lub „Oświadczenie” (ostrzeżenie, nie błąd) i nie zawiera odwołań do przepisów |
| R02 | ≥ 2 strony. Dokładnie jedna `FINISH`, zawsze ostatnia, pozostałe `MAIN` |
| R03 | Każda strona ma ≥ 1 pole. Każde pole leży w `SECTION` lub `REPEATING_SECTION` |
| R04 | Brak zagnieżdżania sekcji w sekcjach |
| R05 | Strona `FINISH` nie zawiera pól do wprowadzania danych (tylko blok tekstu lub sekcję informacyjną, §14, Q1) |
| R06 | Każde pole ma określoną obligatoryjność (§7.2) |
| R07 | Strony połączone `flow.links` w spójny graf od pierwszej strony do `FINISH`, bez wiszących stron |
| R08 | `dictionaryName` tylko w `SELECT`, `RADIO`, `CHECKBOX`. Pole ze słownikiem ma `options: []` |
| R09 | Pola wyboru bez słownika mają ≥ 2 opcje (checkbox pojedynczy: 1) |
| R10 | Pole z danymi inicjalnymi: `readOnly: true`, `defaultValueType: "EXTERNAL_SYSTEM"`, `defaultValue` = `ŹRÓDŁO.atrybut` z katalogu (§8.5) |
| R11 | `states[].type` ∈ {`SHOW`, `READ_ONLY`}. Dla sekcji tylko `SHOW`. `query` kompiluje się w JSONata i odwołuje do istniejących `techName` i tytułów stron |
| R12 | `techName` unikalne. `id` (UUID v4) unikalne |
| R13 | `CONSENT_SECTION` ma ≥ 1 zgodę z `description` i `required` |
| R14 | `INFO_SECTION` ma `description` |
| R15 | Walidatory tylko z listy: `REQUIRED, EMAIL, PESEL, NIP, REGON, ZIP_CODE, EPUAP, ADE, SERIAL_NUMBER_ID_CARD`, i tylko w typach, które je dopuszczają (np. `NUMBER`, `SELECT`, `RADIO` tylko `REQUIRED`) |

### 7.4. Rozbieżności w materiałach i przyjęte decyzje

| # | Rozbieżność | Decyzja |
|---|---|---|
| D1 | Schemat ma `repetingSectionGrid`, wzorce i reguły mają `repeatingSectionGrid` | Generujemy `repeatingSectionGrid` (wzorce = oczekiwany wynik). Schemat w `resources/` poprawiamy lokalnie |
| D2 | Opis typu `CONSENT_SECTIOM` vs `CONSENT_SECTION` | `CONSENT_SECTION` (literówka w opisie) |
| D3 | Reguły: na `FINISH` tylko `INFO_SECTION`. Wzorce: `SECTION` + `TEXT_BLOCK` „Podgląd” | Domyślnie jak wzorce. Przełącznik `FINISH_PAGE_STYLE=sample|info_section` do decyzji po konsultacji (Q1) |
| D4 | Wzorce mają puste `validation`, choć reguły wymagają obligatoryjności | Dodajemy `REQUIRED` (Q2) |
| D5 | Schemat: `defaultValue` string. Wzorzec: `["Polska"]` dla `SELECT` | Jak wzorzec |
| D6 | Wzorce używają kluczy spoza schematu: `multiLevelTree`, `searchEnabled` | Zachowujemy (schemat nie zabrania dodatkowych pól) |
| D7 | Słowniki w dokumencie: Województwo/Powiat/Gmina/Miejscowość/Kraje/Numery kierunkowe. We wzorcach: `TERYT_4G_DOWODOWY` (`multiLevelTree: true`), `TERYT_DOWODOWY`, `Kraje` | Używamy nazw ze wzorców dla adresu (jedno pole wielopoziomowe TERYT). Nazwę słownika numerów kierunkowych ustalamy z mentorami (Q3) |
| D8 | Standard: `FILE_UPLOADER` ma formaty, limit rozmiaru i liczbę plików, ale schemat nie ma na to pól | Wartości wpisujemy do `description` pola (czytelne dla obywatela). Dedykowane klucze tylko po potwierdzeniu (Q4) |
| D9 | Standard wymienia walidację telefonu i wzorzec regex (KRS `^\d{10}$`), lista walidatorów ich nie ma | Telefon: słownik numerów kierunkowych + pole tekstowe bez walidatora. KRS: opis z formatem. Regex tylko po potwierdzeniu klucza (Q5) |
| D10 | Wzorce: pola adresu i kontaktu z `MLPZ.*` nie są `readOnly`, a „Dane inicjalne” wymagają `readOnly` | „Twoje dane” i dane z PESEL: `readOnly`. Adres i kontakt z MLPZ: edytowalne jak we wzorcu, bo standard mówi „możesz je zmienić lub usunąć” (Q6) |
| D11 | Standard opisuje checkboxy „Brak nazwy ulicy / numeru lokalu / kodu pocztowego”, wzorce ich nie mają | Szablon adresu 1:1 ze wzorców, bez checkboxów (opcja renderera). Osobne pola dla Polski i zagranicy (`ulica` / `ulica_zagranica`), sufiks kontekstu przed `_zagranica` |
| D12 | D9 zakładała osobny numer kierunkowy w „Danych do kontaktu”, wzorce i standard go nie mają | Tylko „Numer telefonu” i „Adres e-mail” (MLPZ). `NUMERY_KIERUNKOWE` tylko dla pól z semantyką prefiksu |
| D13 | Wzorce różnią się szczegółami sekcji predefiniowanych (PESEL innej osoby, REGON/KRS, `TERYT_DOWODOWY` vs `TERYT_4G_DOWODOWY`, etykiety uploadów, literówka „pełnomonictwo”) | Źródło główne: wzorzec nadpłaty, uzupełniony o standard (PESEL innej osoby, REGON, KRS). Wszystkie adresy: `TERYT_4G_DOWODOWY` z `multiLevelTree`. Lista odstępstw w `tests/golden/test_reference_forms.py` (`RENAMES`, `DICTIONARY_DEVIATIONS`, `SECTION_RENAMES`) |
| D14 | Układ i opisy we wzorcach | `questionOrder = y`; `rows` sekcji = liczba pól + 1; `description` sekcji zawsze dokumentem HTML (także pustym), niepusty opis pola też HTML; tytuł `TEXT_BLOCK` i `CONSENT_SECTION` pusty |
| D15 | jsonata-python nie obsługuje `\'` w literałach | Tytuł strony lub `techName` z apostrofem trafia do zapytania w cudzysłowie `"…"` (JSONata traktuje oba rodzaje literałów tak samo) |
| D16 | Przykład `FormDraft` w §5.4 jest szerszy niż kontrakt LLM (`docs/superpowers/specs/2026-11-21-llm-models-design.md` §5.2) | Obowiązuje kontrakt LLM: bez `semantic`, `addresses`, `summaryInfo`; `visibleWhen` przez `field_id`. `build/` wykrywa semantykę (walidatory, `Kraje`, `NUMERY_KIERUNKOWE`) z etykiety; adres wnioskodawcy to zawsze „Adres zamieszkania”, siedziby i innej osoby wynikają z `applicant_kinds`; strona końcowa bez „Podsumowania”; propozycje słowników (O2) do czasu nowego źródła nie powstają |
| D17 | Standard (pkt 8) zaleca strony alternatywne, ale link `flow.links` ma tylko `id`, `source`, `target` (`importowanyPlikJsonSchemat.json`, `OpisImportowanegoPlikuJSON.md` l. 41-44; oba wzorce `konfiguracja_form_*.json` mają same liniowe pary). Warunek jest dostępny wyłącznie w `states` (SHOW + JSONata) sekcji i pól, strona (tab) nie ma `states` | Strony alternatywne realizujemy przez warunkową widoczność sekcji (SHOW) na stronach liniowego przepływu; generator `flow.links` pozostaje liniowy i nie dodaje pól spoza schematu. R07 akceptuje jednak grafy z wieloma linkami z jednej strony (osiągalność, dojście do FINISH, brak cykli), więc ręcznie rozgałęziony import nie jest „prostowany” |
| D18 | Standard: powyżej 5 opcji lista rozwijana, także wielokrotnego wyboru. Reguły techniczne opisują `SELECT` jako wybór jednej wartości, schemat importu i oba wzorce nie mają atrybutu wielokrotności (`multiple` i podobnych) | `SELECT` nie wspiera wielokrotnego wyboru, więc wielokrotny wybór zostaje `CHECKBOX` bez względu na liczbę opcji (`SELECT` dałby wybór jednokrotny i zmienił sens pytania). Wyjątek od standardu zgłaszamy mentorom; mapowanie zmienimy, gdy schemat dostanie atrybut wielokrotności |
| D19 | Materiał „Dane inicjalne”: pole zasilane z rejestru ma być `readOnly`. W `initial_data.json` 11 atrybutów MLPZ (telefon, e-mail, kraj, województwo, dzielnica, gmina, miejscowość, kod pocztowy, ulica, nr budynku, nr lokalu) ma `editable: true` | `readOnly` wynika z `editable` katalogu. Oba wzorce mają `MLPZ.postCode/street/building/apartment/phoneNumber/email` z `readOnly: false`, a `MLPZ.name/surname` i `PESEL.*` z `readOnly: true`; standard (ekran wizualizacji) mówi „Możesz je zmienić lub usunąć”. Zostajemy przy wzorcach i katalogu; odstępstwo od litery materiału (rozwinięcie D10) do potwierdzenia (Q6) |
| D20 | Standard: tytuł krótki, bez odwołań do przepisów | `normalize_title` (w buildzie, więc dla szkiców z LLM i z reguł) usuwa wyraźne wzorce (`na podstawie art. …`, `zgodnie z art. …`, `o którym mowa w art. …`, `(Dz. U. … poz. …)`) i zgłasza `W31_TITLE_LEGAL_REFERENCE`. Tytuł, który po czyszczeniu byłby pusty, zostaje bez zmian |
| D21 | Pola przedmiotu sprawy ze szkicu nie miały danych inicjalnych | `apply_initial_data` dopisuje `PESEL.*` / `PESEL_ADDRESS.*` tylko we wniosku składanym wyłącznie we własnym imieniu i tylko dla jednoznacznych etykiet (cała etykieta: data i miejsce urodzenia, imiona rodziców, nazwisko rodowe, drugie imię, stan cywilny, płeć, obywatelstwo, adres zameldowania z częścią adresu), zgodnych typem z katalogiem. Pomijane: etykiety i sekcje dotyczące dziecka, małżonka, pełnomocnika, innej osoby itp., sekcje powtarzalne, pola ze słownikiem, powtórzenia atrybutu w formularzu |

---

## 8. Reguły budowy formularza (wiedza domenowa w kodzie)

Źródło: „HackNation – Standardy i dobre praktyki projektowania formularzy” oraz wzorce. Reguły są zapisane jako kod i szablony JSON, a nie tylko jako prompt, żeby wynik był powtarzalny.

### 8.1. Struktura stron

| Strona | Typ | Zawartość |
|---|---|---|
| 1. „Dane” | MAIN | Urząd/Organ → Podmiot wniosku → Twoje dane → Adres zamieszkania → [Dane podmiotu, Adres siedziby, Potwierdzenie reprezentanta] → [Dane innej osoby, Adres innej osoby] → [Pełnomocnictwo] → [Opłata skarbowa v1/v2] |
| 2…n. Przedmiot wniosku | MAIN | sekcje tematyczne z `subjectPages`, tytuł strony od treści (np. „Informacje o nadpłacie”, „Informacje o budynku”) |
| n+1. „Kontakt i zgody” | MAIN | Dane do kontaktu, załączniki ogólne, Zgody i oświadczenia |
| n+2. „Strona końcowa” | FINISH | (opcjonalnie) Podsumowanie, Podgląd |

Strony przedmiotu dzielimy, gdy szkic ma > `MAX_SECTIONS_PER_PAGE` sekcji albo LLM wskazał odrębne tematy. Strony alternatywne (standard pkt 8) to rozszerzenie. Obecny `flow.links` nie ma warunków, więc stosujemy `SHOW` na sekcjach (§14, Q9).

### 8.2. Sekcje predefiniowane (szablony)

| Sekcja | Kiedy dodajemy | Kluczowe pola i warunki |
|---|---|---|
| Urząd, do którego jest składany wniosek / Organ… | zawsze | `nazwa_urzedu` TEXT_FIELD, `readOnly`, `defaultValue` = adresat odczytany z blankietu |
| Podmiot wniosku | `applicantKinds` ≠ tylko SELF | RADIO „Wybierz, w czyim imieniu wnioskujesz” z opcjami według `applicantKinds`, REQUIRED. RADIO „Wybierz, jako kto wnioskujesz” (Pełnomocnik/Reprezentant), SHOW gdy „Osoby prawnej…” |
| Twoje dane | zawsze | Imię, Nazwisko, Numer PESEL: `readOnly`, EXTERNAL_SYSTEM (`MLPZ.name`, `MLPZ.surname`, `MLPZ.pesel`), PESEL z walidatorem `PESEL` |
| Adres zamieszkania / siedziby / innej osoby | według `addresses` i `applicantKinds` | Kraj (SELECT, `Kraje`, `searchEnabled`, default `["Polska"]`). Dla Polski: TERYT (SELECT wielopoziomowy), kod pocztowy (`ZIP_CODE`), ulica, nr budynku, nr lokalu. Dla innego kraju: miejscowość, kod pocztowy bez walidacji, ulica, nr budynku, nr lokalu. Widoczność przez SHOW na polu „Kraj” |
| Dane innej osoby | OTHER_PERSON | Imię, Nazwisko, PESEL (`PESEL`), SHOW gdy „Innej osoby” |
| Dane podmiotu | LEGAL_ENTITY | Nazwa, NIP (`NIP`), REGON (`REGON`), Numer KRS (opcjonalny), SHOW gdy „Osoby prawnej…” |
| Potwierdzenie, że jesteś reprezentantem | LEGAL_ENTITY | FILE_UPLOADER, SHOW gdy „Reprezentant” |
| Pełnomocnictwo | OTHER_PERSON lub LEGAL_ENTITY | FILE_UPLOADER (jpg, pdf, xml, PAdES, png, jpeg, CAdES, XAdES; 10 MB; 1 plik), SHOW gdy „Innej osoby” lub („Osoby prawnej…” i „Pełnomocnik”) |
| Opłata skarbowa (wersja 1) | OTHER_PERSON | RADIO Tak/Nie, TEXT_BLOCK z kwotą 17 zł i instrukcją (SHOW gdy Tak), FILE_UPLOADER PDF (SHOW gdy Tak) |
| Opłata skarbowa (wersja 2) | LEGAL_ENTITY + Pełnomocnik | TEXT_BLOCK + FILE_UPLOADER PDF |
| Dane do kontaktu | zawsze | Numer telefonu (`MLPZ.phoneNumber`), Adres e-mail (`MLPZ.email`, `EMAIL`), oba opcjonalne |
| Zgody i oświadczenia / Oświadczenie / Zgoda | zawsze (min. zgoda RODO z linkiem do klauzuli) | CONSENT_SECTION. Oświadczenia z blankietu zamieniamy na formy neutralne płciowo w czasie teraźniejszym |
| Podsumowanie | gdy `summaryInfo` | TEXT_BLOCK |
| Podgląd | zawsze | TEXT_BLOCK: „Zanim przejdziesz do wyboru sposobu podpisu, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji.” |

Reguła doboru opcji „Podmiotu wniosku” (standard, s. 10):
- blankiet ma tylko dane osoby fizycznej → `Swoim`, `Innej osoby`;
- tylko dane firmy lub instytucji → `Osoby prawnej lub jednostki organizacyjnej`;
- jedno i drugie → wszystkie trzy opcje.

Szablony powstają przez wycięcie sekcji z dwóch wzorcowych JSON-ów, więc 1:1 odpowiadają oczekiwanemu formatowi. Treści bloków tekstu (opłata skarbowa, podgląd) przepisujemy ze standardu.

### 8.3. Mapowanie typów pól i walidatorów

| `kind` ze szkicu | Typ w JSON | Uwagi |
|---|---|---|
| short_text | TEXT_FIELD | |
| long_text | TEXTAREA | uzasadnienie, opis, uwagi |
| number | NUMBER | kwoty, liczby sztuk, powierzchnie |
| date | DATEPICKER | |
| single_choice, ≤ 5 opcji | RADIO | |
| single_choice, > 5 opcji lub słownik | SELECT | `searchEnabled: true` gdy > 15 opcji lub słownik |
| multi_choice | CHECKBOX | |
| file | FILE_UPLOADER | |
| info | TEXT_BLOCK | nie dla opisu konkretnego pola: wtedy `description` pola |
| zgody, oświadczenia | CONSENT_SECTION | nigdy osobne CHECKBOX/RADIO |

Walidatory na podstawie `semantic` ze szkicu oraz regexów na etykiecie (słownik synonimów PL):

| Wykrycie | Walidator |
|---|---|
| PESEL | `PESEL` |
| NIP | `NIP` |
| REGON | `REGON` |
| kod pocztowy | `ZIP_CODE` |
| e-mail, adres poczty elektronicznej | `EMAIL` |
| ePUAP, skrytka | `EPUAP` |
| adres do e-Doręczeń | `ADE` |
| seria i numer dowodu osobistego | `SERIAL_NUMBER_ID_CARD` |
| oznaczenie wymagalności (`*`, „wymagane”, brak „(opcjonalnie)”) lub decyzja LLM | `REQUIRED` |

Tekst pól redagujemy według zasad „Głos i ton”: etykiety krótkie, bez form bezosobowych, wyjaśnienia w `description` lub `tooltipMessage`. Robi to LLM na etapie szkicu, a kod sprawdza tylko długość (ostrzeżenie przy etykiecie > 80 znaków).

### 8.4. Słowniki (O1)

Katalog w `resources/dictionaries.json`:

| `dictionaryName` | Zastosowanie | Typ pola |
|---|---|---|
| `Kraje` | kraj adresu, obywatelstwa, urodzenia | SELECT |
| `TERYT_4G_DOWODOWY` (`multiLevelTree: true`) | województwo → powiat → gmina → miejscowość w adresie polskim | SELECT |
| `TERYT_DOWODOWY` | wariant TERYT użyty we wzorcu dla adresu innej osoby | SELECT |
| Województwo / Powiat / Gmina / Miejscowość | wariant z osobnymi polami (jeśli import tego wymaga, Q3) | SELECT |
| Numery kierunkowe | prefiks telefonu | SELECT |

Powiązanie: semantyka pola (adres, kraj, prefiks telefonu) → słownik. Pole dostaje `dictionaryName`, `options: []` i `searchEnabled: true`.

### 8.5. Dane inicjalne (O1)

Katalog w `resources/initial_data.json` przepisany z „Dane inicjalne…”: źródła `PESEL` (16 atrybutów), `PESEL_ADDRESS` (18), `MLPZ` (17), z typem pola dla każdego atrybutu.

Reguły:
- „Twoje dane” → `MLPZ.name/surname/pesel` (zgodnie ze standardem, „…z MLPZ”). Wzorzec nadpłaty używa `PESEL.*`, więc źródło jest konfigurowalne (`INITIAL_DATA_IDENTITY_SOURCE=MLPZ|PESEL`).
- Pola, które formularz zbiera o wnioskodawcy, a które są w rejestrze (data urodzenia, imiona rodziców, adres zameldowania), mapujemy na `PESEL.*` / `PESEL_ADDRESS.*` z `readOnly: true` (standard pkt 6: „korzystaj z danych dostępnych w rejestrach”).
- Typ pola musi zgadzać się z typem atrybutu (`birthDate` → DATEPICKER).
- Jedno pole = jedno źródło i jeden atrybut.

### 8.6. Propozycje nowych słowników (O2)

Gdy pole wyboru ma listę opcji o charakterze zamkniętym i ogólnokrajowym (nie zależy od urzędu), a w katalogu brakuje słownika, to:
1. w JSON pole dostaje **opcje inline** (formularz importuje się i działa od razu);
2. w raporcie (`dictionaryProposals`) pojawia się propozycja: nazwa (`UPPER_SNAKE_CASE`), struktura pozycji (`code`, `name`, `techName`, opcjonalnie `validFrom`/`validTo`), lista pozycji i pola, które jej użyją. Endpoint `/dictionaries` zwraca propozycje oznaczone `"status": "PROPOSED"`.

Przykłady z dostarczonych blankietów (do potwierdzenia przy implementacji):
- `RASY_PSOW_AGRESYWNYCH`: wniosek o zezwolenie na utrzymywanie psa rasy uznawanej za agresywną, lista ras z rozporządzenia MSWiA;
- `RODZAJE_PODATKOW_LOKALNYCH`: wniosek o stwierdzenie nadpłaty, pole „Nazwa podatku”;
- `RODZAJE_ZAJECIA_PASA_DROGOWEGO`: wniosek o zajęcie pasa drogowego;
- `RODZAJE_DOKUMENTOW_TOZSAMOSCI`: pola typu „rodzaj dokumentu”.

### 8.7. Zależności dynamiczne (O3)

`visibleWhen` ze szkicu i warunki z sekcji predefiniowanych zamieniamy na JSONata według szablonów z „Reguł technicznych”:

| Przypadek | Szablon `query` |
|---|---|
| pole wyboru w zwykłej sekcji | `("{wartość}" in tabs['{tytuł strony}' in title].questions['{techName sekcji}' in field.techName].field.repeatingSectionGrid['{techName pola}' in field.techName].field.__userAnswer)` |
| pole w sekcji powtarzającej się | `"{wartość}" in tabs['{tytuł strony}' in title].questions['{techName sekcji}' in field.techName].field.__userAnswer[$repeatingSectionIndex]['{techName pola}' in fieldTechName].answers` |
| negacja („inny niż Polska”) | `$not(<warunek równości>)` |
| koniunkcja / alternatywa | `(<w1>) and (<w2>)` / `(<w1>) or (<w2>)` |

- `SHOW` dla pól i sekcji, `READ_ONLY` dla pól (np. pole zablokowane po zaznaczeniu checkboxa „Brak numeru lokalu”).
- Warunek może wskazywać pole z innej strony. Wtedy w zapytaniu używamy tytułu tamtej strony.
- Każde zapytanie kompilujemy (jsonata-python) i testujemy na syntetycznym modelu odpowiedzi: dla wartości warunku musi dać `true`, dla innej `false`. Zapytanie, które nie przejdzie testu, usuwamy z ostrzeżeniem (§5.6).

---

## 9. Frontend (O4, O5, O6)

### 9.1. Widoki

| Widok | Funkcje |
|---|---|
| Logowanie | formularz login/hasło → JWT w NgRx Store (slice `auth`), kopia w `sessionStorage` przywracana przy starcie (meta-reducer), bez localStorage. Automatyczne wylogowanie po wygaśnięciu |
| Import (batch) | drag & drop wielu plików, walidacja po stronie klienta (te same reguły co §6.3 pkt 2–5), kolejka ze statusem pliku (oczekuje / przetwarzanie / gotowe / błąd), równoległość ograniczona do `BATCH_CONCURRENCY` (domyślnie 2), ponowienie pojedynczego pliku, pobranie wszystkich wyników jako ZIP (generowany w przeglądarce) |
| Wynik | 3 zakładki: **Podgląd formularza**, **JSON** (drzewo + surowy tekst, kopiuj, pobierz `.json`), **Raport** (ostrzeżenia z linkiem do miejsca w JSON, propozycje słowników, statystyki, czas) |
| Walidator | wklejenie lub wgranie JSON → `/forms/validate` → lista błędów |

Batch to sekwencja pojedynczych wywołań `/forms/convert`, więc API pozostaje zgodne z wymogiem „pojedynczy plik na żądanie”.

### 9.2. Komponenty

```
frontend/src/app/
  core/       auth.interceptor.ts, api.service.ts, error.interceptor.ts
  store/
    auth/          auth.actions.ts, auth.reducer.ts, auth.effects.ts, auth.selectors.ts
    import-queue/  import-queue.actions.ts, .reducer.ts (EntityAdapter), .effects.ts (batch, concurrency), .selectors.ts
    catalog/       catalog.actions.ts, .reducer.ts, .effects.ts, .selectors.ts
  features/
    login/
    import/    import-page, file-queue (selectSignal z import-queue), file-drop.directive
    result/    result-page, json-viewer, report-panel
    preview/   form-renderer, tab-stepper, section, field-host + komponent na typ pola,
               states.service.ts (jsonata), validators.ts (PESEL, NIP, REGON, kod, e-mail…),
               dictionaries.mock.ts (Kraje, TERYT – próbki do podglądu)
  shared/     models/form-definition.ts (typy wygenerowane z OpenAPI)
```

### 9.3. Renderer formularza (O5)
- Strony jako stepper. Nawigacja według `flow.links`, przycisk „Dalej” blokowany przy błędach walidacji na stronie.
- Sekcje i pola w CSS Grid: `grid-area: {y+1} / {x+1} / span {rows} / span {cols}` (wzór z opisu JSON).
- Model odpowiedzi w strukturze zgodnej z zapytaniami (`field.__userAnswer`). Po każdej zmianie ewaluujemy `states` przez bibliotekę `jsonata` i pokazujemy lub ukrywamy elementy, a pola `READ_ONLY` blokujemy.
- Walidatory po stronie klienta: PESEL (suma kontrolna), NIP (wagi), REGON 9/14 (wagi), kod pocztowy `^\d{2}-\d{3}$`, e-mail, ePUAP, ADE (format adresu e-Doręczeń), seria i numer dowodu (3 litery + 6 cyfr, suma kontrolna).
- Pola z danymi inicjalnymi pokazują przykładowe wartości testowe (np. „Jan Kowalski”) i oznaczenie „dane z rejestru”.
- Dostępność: WCAG 2.1 AA (standard pkt 1): etykiety `for`/`id`, `aria-describedby` dla opisów i błędów, fokus na pierwszym błędzie, kontrast, obsługa klawiatury.

### 9.4. Makiety
Do repozytorium dołączamy makiety trzech głównych widoków (Import, Wynik/Podgląd, Raport) jako zrzuty ekranu działającej aplikacji. To też materiał do prezentacji i filmu.

---

## 10. Bezpieczeństwo

### 10.1. Uwierzytelnianie
- JWT (HS256 domyślnie, RS256 opcjonalnie przez `JWT_PUBLIC_KEY`/`JWT_PRIVATE_KEY`). Konfigurowalne: `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_EXPIRES_MIN`, `JWT_LEEWAY_S`.
- RS256 z samym kluczem publicznym = tryb tylko weryfikacji: tokeny wydaje inny system (np. COI), `/auth/token` nie jest rejestrowany. Klucz podawany statycznie (env lub Docker secret) – bez JWKS i bez ruchu sieciowego (§14, Q10).
- Weryfikujemy podpis, `exp`, `nbf`, `iat`, `iss`, `aud`, `sub`. Algorytm z konfiguracji, nigdy z nagłówka tokenu (`alg=none` odrzucane).
- Konto techniczne: `API_USER` + `API_PASSWORD_HASH` (argon2id przez `argon2-cffi`, MIT; hash generuje `make password-hash`). Hasło nie trafia do obrazu, tylko do zmiennych środowiskowych w runtime.
- Mapowanie claimów tokenów z brokera tożsamości: `JWT_SUBJECT_CLAIM` (domyślnie `sub`), `JWT_ROLES_CLAIM` (domyślnie `roles`, ścieżka z kropkami dla claimów zagnieżdżonych) i `JWT_REQUIRED_ROLE` (pusta = brak wymogu; brak roli w tokenie → 403 `FORBIDDEN`).
- Ścieżka wdrożenia z Węzłem Krajowym (login.gov.pl) przez broker tożsamości: `docs/architecture/wezel-krajowy.md`.
- Szczegóły: `docs/superpowers/specs/2026-11-21-auth-core-design.md`.
- Opcjonalnie `AUTH_ENABLED=false` dla lokalnego dewelopmentu. W trybie produkcyjnym aplikacja odmawia startu z tym ustawieniem.

### 10.2. Plik wejściowy jako dane niezaufane
- Walidacja z §6.3, łącznie z bombami ZIP, limitem pikseli i liczby stron.
- XML z DOCX/XLSX/ODS parsowany przez `defusedxml` (brak XXE).
- LibreOffice: osobny proces, timeout, katalog tymczasowy per żądanie, brak sieci w kontenerze `api` poza siecią wewnętrzną do `llm`.
- Limit równoległych konwersji (`MAX_CONCURRENT_JOBS`, semafor), żeby nie wyczerpać CPU i RAM.
- Treść dokumentu trafia do LLM jako dane, w wydzielonym bloku. Wynik modelu jest ograniczony schematem i weryfikowany regułami (§4.3), więc *prompt injection* nie może wywołać akcji. Najgorszy skutek to błędny szkic, który i tak przechodzi walidację strukturalną.

### 10.3. Przechowywanie danych (M5)
- Upload strumieniowo do `SpooledTemporaryFile` (w pamięci do `SPOOL_MAX_MB`, potem na tmpfs).
- Każde żądanie ma własny `TemporaryDirectory`, usuwany w `finally`, także przy błędzie i timeoucie.
- `/tmp` w kontenerze to `tmpfs`, a system plików kontenera jest `read_only: true`.
- Logi nie zawierają treści dokumentu ani wyniku, tylko metadane (nazwa pliku skrócona do hash, rozmiar, czasy, kody ostrzeżeń).

### 10.4. HTTP
- CORS: tylko origin frontendu (`CORS_ORIGINS`).
- Nagłówki bezpieczeństwa w nginx: CSP, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`.
- Limit rozmiaru żądania w nginx i w API (ta sama wartość).

---

## 11. Konteneryzacja (M6)

### 11.1. Obrazy

| Usługa | Obraz bazowy (wersje jawne, bez `latest`) | Użytkownik | Port |
|---|---|---|---|
| api | `python:3.14-alpine3.22` (multi-stage: builder z `uv`, runtime z `tesseract-ocr`, `tesseract-ocr-data-pol`, `tesseract-ocr-data-osd` (orientacja skanów), `libmagic`, `libreoffice-writer`, `libreoffice-calc`) | `app` (UID 10001, bez powłoki logowania) | 8000 |
| frontend | build: `node:24-alpine3.22`. Runtime: `nginx:1.28-alpine3.22` (nasłuch 8080, pid i cache w `/tmp`) | `nginx` (nie root) | 8080 |
| llm | `ubuntu:24.04@sha256:…` + binarka i biblioteki CPU skopiowane z `ollama/ollama:0.40.16@sha256:…` (`llm/Dockerfile`, target `cpu`; bez bibliotek NVIDIA CUDA/cuDNN o licencji własnościowej). Target `gpu` = obraz producenta, tylko z `docker-compose.gpu.yml` | `ollama` (UID 10002) | 11434 (tylko sieć wewnętrzna) |

Wszystkie obrazy przypinamy do konkretnej wersji (najlepiej z digestem `@sha256:` w compose dla wydania do oceny).

Alpine dla `api` jest możliwe, bo celowo **nie używamy PyTorcha** (ekstrakcja: pdfplumber + Tesseract, model w osobnym kontenerze). Jeśli któraś zależność nie ma kół `musllinux` dla 3.14, fallbackiem jest `python:3.14-slim-trixie` z uzasadnieniem w README (§14, R2).

### 11.2. docker-compose (zarys)

```yaml
services:
  api:
    build: ./backend
    env_file: .env                 # sekrety tylko w runtime, .env poza repo (.env.example w repo)
    read_only: true
    tmpfs: [ "/tmp:size=512m" ]
    cap_drop: [ "ALL" ]
    security_opt: [ "no-new-privileges:true" ]
    depends_on: { llm: { condition: service_healthy } }
    networks: [ internal, public ]
    ports: [ "8000:8000" ]
    healthcheck: { test: ["CMD", "wget", "-qO-", "http://localhost:8000/api/v1/health/live"] }
  frontend:
    build: ./frontend
    read_only: true
    tmpfs: [ "/tmp" ]
    ports: [ "8080:8080" ]
    networks: [ public ]
  llm:
    image: ollama/ollama:<pin>
    volumes: [ "ollama-models:/root/.ollama" ]
    networks: [ internal ]          # bez portu na hoście
    healthcheck: { test: ["CMD", "ollama", "list"] }
networks:
  internal: { internal: true }
  public: {}
volumes:
  ollama-models: {}
```

- Model pobieramy raz przy instalacji (`make model` → `docker compose --profile setup run --rm llm-pull`: ten sam obraz i wolumen co `llm`, ale w sieci `egress`, bo `internal` nie ma wyjścia do internetu) albo dostarczamy jako wolumen offline (README). W trakcie działania nie ma ruchu do internetu.
- Rzeczywisty `docker-compose.yml` dodaje do zarysu: `init: true` dla `api` (tini zbiera procesy LibreOffice), `pids_limit`, `read_only` i `cap_drop` także dla `llm`, healthcheck frontendu, porty `API_PORT`/`FRONTEND_PORT` oraz `scripts/init-env.sh` do wygenerowania `.env`.
- Kontener `llm` i pobieranie modelu są opcjonalne: profil `ollama` (`COMPOSE_PROFILES=ollama` w `.env`, domyślnie). Bez profilu `api` startuje samo (`depends_on` z `required: false`) i łączy się z zewnętrznym serwerem modelu pod `LLM_BASE_URL`; `extra_hosts: host.docker.internal` pozwala wskazać serwer na hoście.
- GPU: `docker-compose.gpu.yml` (nakładka `-f`) buduje target `gpu` (obraz producenta z CUDA) i dodaje `deploy.resources.reservations.devices` dla NVIDIA.
- `OLLAMA_NO_CLOUD=1`: Ollama nie próbuje łączyć się z ollama.com (katalog modeli w chmurze, podpowiedzi modeli).
- Sekrety (`JWT_SECRET`, `API_PASSWORD_HASH`) tylko przez `env_file` lub Docker secrets, nigdy przez `ARG`/`ENV` w Dockerfile.

---

## 12. Konfiguracja (M7)

Wszystkie parametry przez zmienne środowiskowe (pydantic-settings). Plik `.env.example` w repozytorium.

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `APP_ENV` | `production` | `production` / `development` |
| `MAX_FILE_SIZE_MB` | `20` | maks. rozmiar uploadu (**wymóg**) |
| `MAX_UNCOMPRESSED_MB` | `100` | limit dekompresji DOCX/XLSX/ODS |
| `MAX_PDF_PAGES` | `30` | |
| `MAX_IMAGE_PIXELS` | `100000000` | długie skany z wieloma stronami A4 w jednym obrazie (1654 × 37 424 px = 16 stron w materiałach) |
| `SPOOL_MAX_MB` | `10` | próg przejścia z RAM na tmpfs |
| `MAX_CONCURRENT_JOBS` | `2` | równoległe konwersje |
| `REQUEST_TIMEOUT_S` | `540` | całkowity czas przetwarzania |
| `AUTH_ENABLED` | `true` | |
| `JWT_SECRET` | — (wymagany) | sekret HS256 (**wymóg**) |
| `JWT_ALGORITHM` | `HS256` | `HS256` / `RS256` |
| `JWT_PUBLIC_KEY` / `JWT_PRIVATE_KEY` | — | dla RS256 |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `coi-cf` / `coi-cf-api` | |
| `JWT_EXPIRES_MIN` | `60` | |
| `JWT_LEEWAY_S` | `30` | tolerancja różnicy zegarów (exp/nbf/iat) |
| `JWT_SUBJECT_CLAIM` | `sub` | claim z identyfikatorem użytkownika (np. `preferred_username`) |
| `JWT_ROLES_CLAIM` | `roles` | claim z rolami, ścieżka z kropkami (np. `realm_access.roles`) |
| `JWT_REQUIRED_ROLE` | — | rola wymagana do korzystania z API; pusta = brak wymogu |
| `API_USER` / `API_PASSWORD_HASH` | — (wymagane) | konto techniczne |
| `CORS_ORIGINS` | `http://localhost:8080` | |
| `LLM_BASE_URL` | `http://llm:11434` | parametr integracyjny |
| `LLM_MODEL` | `qwen3:8b` | model analizy (jeden; przy niepoprawnym szkicu jedna ponowna próba) |
| `LLM_TIMEOUT_S` | `240` | limit jednego wywołania modelu |
| `LLM_TEMPERATURE` / `LLM_SEED` | `0` / `42` | powtarzalność |
| `LLM_NUM_CTX` | `8192` | okno kontekstu (prompt z przykładem ok. 3 tys. tokenów + odpowiedź; większe okno tylko zajmuje RAM) |
| `EXTRACTION_VLM_ENABLED` / `VLM_MODEL` | `false` / `qwen2.5vl:7b` | tryb wizyjny dla skanów |
| `OCR_LANG` | `pol` | |
| `OCR_DPI` | `300` | |
| `CONVERTER_TIMEOUT_S` | `60` | LibreOffice |
| `INITIAL_DATA_IDENTITY_SOURCE` | `MLPZ` | źródło „Twoje dane” |
| `FINISH_PAGE_STYLE` | `sample` | D3 |
| `MAX_SECTIONS_PER_PAGE` | `8` | podział stron przedmiotu |
| `LOG_LEVEL` | `INFO` | logi JSON na stdout |

Aplikacja waliduje konfigurację przy starcie i nie uruchamia się bez wymaganych sekretów.

---

## 13. Jakość, testy, wymagania niefunkcjonalne

### 13.1. Testy

| Poziom | Zakres | Narzędzie |
|---|---|---|
| Jednostkowe | walidacja uploadu (każdy przypadek z §6.3), slug `techName`, walidatory PESEL/NIP/REGON, generator JSONata, layout, reguły R01–R15 | pytest |
| Ekstrakcja | dla każdego formatu z `` `DocumentModel` zawiera kluczowe etykiety (lista oczekiwanych fraz per formularz) | pytest |
| Golden | 2 formularze z wzorcowymi JSON-ami: wynik vs wzorzec, metryka podobieństwa strukturalnego (pokrycie sekcji po tytule, pokrycie pól po `techName`/etykiecie, zgodność typów, zgodność `states`). Próg regresji w CI | pytest + własny skrypt `scripts/compare.py` |
| Kontraktowe | każdy wynik przechodzi JSON Schema i reguły R01–R15 | pytest |
| E2E API | wszystkie pliki z `` (9 formularzy × do 8 formatów) → 200 + poprawny JSON. Błędne pliki → właściwe kody | pytest + httpx |
| Frontend | reducery i selektory (czyste funkcje), effects (`provideMockActions`), komponenty renderera, ewaluacja `states`, walidatory | Vitest + `@ngrx/store/testing` |
| E2E UI | logowanie → upload → podgląd → przełączenie opcji pokazuje sekcję | Playwright |
| Licencje | brak GPL/AGPL/LGPL/SSPL | pip-licenses, license-checker |
| Statyczna analiza | lint, typy, formatowanie | ruff, mypy (strict), ESLint, Prettier |

LLM w testach jednostkowych mockujemy (zapisane odpowiedzi). Testy golden i E2E uruchamiamy z prawdziwym modelem w osobnym jobie.

### 13.2. Wymagania niefunkcjonalne (cele do zmierzenia)

| Obszar | Cel |
|---|---|
| Czas konwersji (CPU 8 rdzeni, 16 GB RAM, formularz 1–3 strony) | p50 ≤ 120 s, p95 ≤ 300 s |
| Czas konwersji z GPU (≥ 8 GB VRAM) | p50 ≤ 15 s |
| Zasoby | api ≤ 1 GB RAM. llm ≤ 8 GB RAM (model 8B Q4) |
| Poprawność strukturalna | 100% wyników przechodzi JSON Schema i R01–R15 (wymuszone kodem) |
| Jakość merytoryczna | pokrycie pól wzorca ≥ 85% na dwóch formularzach golden |
| Powtarzalność | ten sam plik daje ten sam JSON (z dokładnością do UUID) |
| Obserwowalność | logi JSON z `request_id` i czasami etapów pipeline'u |
| Uruchomienie | `docker compose up` + jednorazowe pobranie modelu. Bez innych kroków |

### 13.3. Generowanie plików wynikowych do oceny
Skrypt `scripts/convert_all.py` przepuszcza wszystkie formularze z katalogu wejściowego przez API i zapisuje `out/<nazwa>.json` oraz `out/<nazwa>.report.json`. Wynikowe JSON-y idą do zgłoszenia (wymóg formalny pkt 4).

---

## 14. Otwarte pytania (do mentorów COI) i ryzyka

### 14.1. Pytania

| # | Pytanie | Domyślna decyzja do czasu odpowiedzi |
|---|---|---|
| Q1 | Strona FINISH: `INFO_SECTION` (reguły) czy `SECTION` + `TEXT_BLOCK` (wzorce)? | wzorce, przełącznik `FINISH_PAGE_STYLE` |
| Q2 | Jak wyrażać obligatoryjność: `"REQUIRED"` w `validation`? Wzorce mają puste tablice | `REQUIRED` w `validation` |
| Q3 | Dokładne `dictionaryName` dla województwa/powiatu/gminy/miejscowości i numerów kierunkowych | `TERYT_4G_DOWODOWY`, `Kraje`, numery kierunkowe: `NUMERY_KIERUNKOWE` |
| Q4 | Czy import obsługuje klucze dla `FILE_UPLOADER` (formaty, rozmiar, liczba plików)? | informacja w `description` |
| Q5 | Czy jest klucz na własny regex i komunikat (KRS, telefon)? | brak, informacja w opisie |
| Q6 | Czy adres i kontakt z MLPZ mają być `readOnly`? | edytowalne, jak we wzorcach |
| Q7 | Czy LibreOffice (MPL-2.0, osobny proces) jest akceptowalny? | tak, z uzasadnieniem w README |
| Q8 | Czy akceptować `.jpe` / `.jfif`? | nie (415) |
| Q9 | Czy `flow.links` może mieć warunki (strony alternatywne)? | nie, zamiast tego `SHOW` na sekcjach |
| Q10 | Czy weryfikacja tokenów RS256 wydanych przez system COI (klucz publiczny w konfiguracji) jest pożądana? | wspieramy konfiguracją; domyślnie HS256 i własne tokeny |
| Q11 | Czy Generator Formularzy COI ma już logowanie (SSO, Węzeł Krajowy), pod które powinno się podpiąć nasze API? | ścieżka przez broker tożsamości, `docs/architecture/wezel-krajowy.md` |

### 14.2. Ryzyka

| # | Ryzyko | Mitygacja |
|---|---|---|
| R1 | Słaba jakość OCR skanów (krzywe zdjęcia, pismo) | preprocessing, Tesseract OSD, opcjonalny model wizyjny, ostrzeżenie `W12_LOW_OCR_CONFIDENCE` |
| R2 | Brak kół dla Python 3.14 / musl w którejś zależności | wczesny spike budowy obrazu (dzień 1). Fallback `python:3.14-slim` |
| R3 | Czas inferencji na CPU podczas obrony | mały model Q4, rozgrzanie modelu przy starcie (`keep_alive`), profil GPU, pomiar czasu na sprzęcie demo |
| R4 | Halucynacje LLM (pola, których nie ma na blankiecie) | ekstrakcja jako źródło prawdy: pole ze szkicu bez dopasowania do tekstu dokumentu (fuzzy match etykiety) dostaje ostrzeżenie. Temperatura 0 |
| R5 | Nieznane formularze na obronie | reguły ogólne + sekcje predefiniowane + degradacja zamiast błędu (§5.6). Test na wszystkich 9 typach blankietów |
| R6 | Rozbieżności w materiałach (§7.4) | konfigurowalne przełączniki, szybkie pytania do mentorów |

---

## 15. Dokumentacja i dostarczenie (M8, wymogi formalne)

- `README.md`: wymagania sprzętowe, budowa obrazów (`docker compose build`), pobranie modelu, uruchomienie, tabela konfiguracji (§12), opis REST API z przykładami `curl` (§6), uruchomienie testów, informacja o licencjach.
- ``: diagram kontenerów i pipeline'u, decyzje (§4.3, §7.4) w formie krótkich ADR.
- OpenAPI dostępne w działającej aplikacji (`/docs`) i wyeksportowane do ``.
- Zgłoszenie: tytuł i opis projektu, prezentacja PDF (≤ 10 slajdów), wynikowe pliki JSON (`out/`), film ≤ 3 min (link do otwartego repozytorium wideo), link do repozytorium kodu, zrzuty ekranu i makiety.

### 15.1. Proponowana struktura repozytorium

```
/backend            FastAPI + pipeline + testy
/frontend           Angular
/docs               materiały wejściowe, specyfikacja, architektura, openapi.json
/scripts            convert_all.py, compare.py
/out                wynikowe JSON-y do zgłoszenia
docker-compose.yml
.env.example
Makefile            build, up, model, test, convert-all
README.md
```

### 15.2. Kolejność realizacji (od wymogów obowiązkowych do punktowanych)

1. Szkielet API + walidacja uploadu + JWT + Docker (M1, M4–M7). Spike obrazu Alpine/3.14.
2. Ekstrakcja wszystkich formatów → `DocumentModel` + testy na ``.
3. Szablony sekcji predefiniowanych z wzorców + builder + weryfikator (R01–R15). Degradacja bez LLM działa już tutaj.
4. Integracja LLM (szkic, structured output) + testy golden.
5. Słowniki, dane inicjalne, walidatory, JSONata (O1, O3, O6).
6. Frontend: import, batch, JSON, raport (O4). Potem renderer z `states` (O5).
7. Propozycje słowników (O2), dopracowanie tekstów, generowanie `out/`, README, prezentacja, film.
