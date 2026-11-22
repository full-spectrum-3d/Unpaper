# Unpaper – konwersja blankietów na formularze e-usług

HackNation 2026, wyzwanie COI „Cyfryzacja formularzy”. Usługa REST przyjmuje blankiet
(PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) i zwraca JSON z konfiguracją formularza
gotową do importu w Generatorze Formularzy COI. Do usługi dołączona jest aplikacja
webowa (import wielu plików, podgląd formularza, raport, pobranie JSON).

Zasada działania: **AI rozumie, kod buduje**. Model językowy (Qwen3 8B przez Ollama)
tylko odczytuje z dokumentu, jakie dane są potrzebne; JSON składa deterministyczny kod,
więc wynik jest poprawny strukturalnie także bez modelu (wtedy szkic powstaje z reguł).

```
frontend (nginx :8080) ──/api──▶ api (FastAPI, Python 3.14 :8000) ──▶ llm (Ollama :11434)
```

Pipeline API: walidacja pliku → normalizacja (LibreOffice) → ekstrakcja (tekst, OCR)
→ analiza AI → budowa formularza → weryfikacja z autonaprawą.
Szczegóły: `docs/specyfikacja-techniczna.md`, `docs/architecture/`.

## Budowanie obrazów Docker

Wymagany Docker Engine 24+ z Compose v2.20+.

```bash
docker compose build            # wszystkie obrazy
docker compose build api        # tylko API
```

Albo pojedynczo:

```bash
docker build -t coi-cf-api:0.1.0 backend
docker build -t coi-cf-frontend:0.1.0 frontend
docker build -t coi-cf-llm:0.40.16 llm
```

| Obraz | Dockerfile | Baza | Port |
|---|---|---|---|
| `coi-cf-api` | `backend/Dockerfile` | `python:3.14-alpine` | 8000 |
| `coi-cf-frontend` | `frontend/Dockerfile` | `node:24-alpine` → `nginx:alpine` | 8080 |
| `coi-cf-llm` | `llm/Dockerfile` | Ollama (CPU; GPU: target `gpu`) | 11434 (tylko sieć wewnętrzna) |

Obrazy nie zawierają sekretów ani modelu. Wszystkie działają jako użytkownik bez roota.

## Uruchomienie aplikacji

```bash
make setup     # .env z sekretami + obrazy + pobranie modelu (można powtórzyć)
make up        # start w tle
```

Bez `make`:

```bash
docker compose build
scripts/init-env.sh                                # tworzy .env i wypisuje hasło konta admin
docker compose --profile setup run --rm llm-pull   # model qwen3:8b do wolumenu (jednorazowo)
docker compose up -d
```

Własny login i hasło: `API_PASSWORD='…' scripts/init-env.sh nazwa_uzytkownika`.

| Adres | Co |
|---|---|
| http://localhost:8080 | aplikacja webowa (logowanie lub rejestracja) |
| http://localhost:8000/docs | Swagger UI (tylko `APP_ENV=development`) |
| http://localhost:8000/api/v1/health/ready | gotowość: 200 = model dostępny |

```bash
docker compose ps            # stan usług
docker compose logs -f api   # logi API
make down                    # zatrzymanie
```

Warianty:

- **Zewnętrzny serwer modelu:** w `.env` `COMPOSE_PROFILES=` (pusto) i `LLM_BASE_URL=https://…`;
  compose uruchomi tylko `api` i `frontend`.
- **GPU NVIDIA:** `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`
  (wymaga NVIDIA Container Toolkit).
- **Konwersja wsadowa:** `make convert-all` (`materials/*` → `out/*.json`).

Na samym CPU konwersja trwa zwykle 1,5–5 min; na GPU kilkanaście sekund.

## Konfiguracja

Zmienne środowiskowe, wczytywane z `.env` (wzór z komentarzami: `.env.example`).
Zmienna ustawiona w środowisku ma pierwszeństwo przed plikiem. W produkcji API nie
wystartuje bez sekretów JWT i konta technicznego.

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `APP_ENV` | `production` | `production` / `development` |
| `LOG_LEVEL` | `INFO` | logi JSON na stdout, bez treści dokumentów |
| `CORS_ORIGINS` | `http://localhost:8080` | dozwolone originy, po przecinku |
| `MAX_FILE_SIZE_MB` | `20` | maksymalny rozmiar pliku (413 `FILE_TOO_LARGE`) |
| `MAX_UNCOMPRESSED_MB` | `100` | limit rozmiaru po dekompresji DOCX / XLSX / ODS |
| `MAX_PDF_PAGES` | `30` | maksymalna liczba stron PDF |
| `MAX_IMAGE_PIXELS` | `100000000` | maksymalna liczba pikseli obrazu |
| `MAX_CONCURRENT_JOBS` | `2` | równoległe konwersje; kolejne czekają |
| `REQUEST_TIMEOUT_S` | `540` | całkowity czas żądania; po nim 504 |
| `AUTH_ENABLED` | `true` | `false` tylko z `APP_ENV=development` |
| `JWT_ALGORITHM` | `HS256` | `HS256` albo `RS256` |
| `JWT_SECRET` | — | sekret HS256, min. 32 bajty |
| `JWT_PUBLIC_KEY` / `JWT_PRIVATE_KEY` | — | klucze PEM dla RS256; bez prywatnego API tylko weryfikuje tokeny |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `coi-cf` / `coi-cf-api` | wymagane `iss` / `aud` |
| `JWT_EXPIRES_MIN` | `60` | ważność tokenu |
| `JWT_SUBJECT_CLAIM` / `JWT_ROLES_CLAIM` / `JWT_REQUIRED_ROLE` | `sub` / `roles` / — | mapowanie claimów brokera tożsamości; brak wymaganej roli → 403 |
| `API_USER` / `API_PASSWORD_HASH` | — | konto techniczne; hash: `make password-hash`, w `.env` w pojedynczych cudzysłowach |
| `REGISTRATION_ENABLED` | `true` | samodzielna rejestracja kont (SQLite na wolumenie `api-data`) |
| `COMPOSE_PROFILES` | `ollama` | pusto = zewnętrzny serwer modelu |
| `LLM_BASE_URL` | `http://llm:11434` | adres serwera modelu (API Ollama) |
| `LLM_AUTH_KEY` / `LLM_AUTH_SECRET` | — | dane proxy auth serwera modelu (np. Modal) |
| `LLM_MODEL` | `qwen3:8b` | model; `LLM_MODELS` – dodatkowe do wyboru przez `?model=` |
| `LLM_TIMEOUT_S` | `240` | limit jednego wywołania modelu; po nim szkic z reguł |
| `LLM_NUM_CTX` / `LLM_NUM_PREDICT` | `8192` / `2048` | okno kontekstu / limit tokenów odpowiedzi |
| `LLM_MAX_CHUNK_CHARS` | `4500` | rozmiar fragmentu dokumentu wysyłanego do modelu |
| `LLM_TEMPERATURE` / `LLM_SEED` | `0` / `42` | powtarzalność wyników |
| `OCR_LANG` / `OCR_DPI` | `pol` / `300` | Tesseract |
| `CONVERTER_TIMEOUT_S` | `60` | limit konwersji LibreOffice |
| `INITIAL_DATA_IDENTITY_SOURCE` | `MLPZ` | źródło danych „Twoje dane”: `MLPZ` / `PESEL` |
| `FINISH_PAGE_STYLE` | `info_section` | układ strony końcowej (`sample` – jak we wzorcach) |
| `MAX_SECTIONS_PER_PAGE` | `8` | limit sekcji na stronę |
| `RODO_CLAUSE_URL` | — | adres `https://` klauzuli RODO linkowanej w zgodzie |
| `API_PORT` / `FRONTEND_PORT` | `8000` / `8080` | porty na hoście (zmienne Compose) |
| `API_MEM_LIMIT` / `LLM_MEM_LIMIT` | `2g` / `10g` | limity pamięci kontenerów (zmienne Compose) |

Sekrety można podać też jako Docker secrets: `/run/secrets/<nazwa_małymi_literami>`.

## REST API

Prefiks `/api/v1`. Pełny opis OpenAPI: `docs/openapi.json` (oraz `/docs` w trybie
`development`). Wszystkie endpointy poza `/auth/*` i `/health/*` wymagają nagłówka
`Authorization: Bearer <JWT>`. Każda odpowiedź ma `X-Request-ID`.

| Metoda | Ścieżka | Wejście | Odpowiedź |
|---|---|---|---|
| POST | `/auth/token` | form: `username`, `password` | `200 {access_token, token_type, expires_in}`; 401 |
| POST | `/auth/register` | JSON: `username`, `password` | `201` jak wyżej; 403 (wyłączona), 409 (login zajęty) |
| GET | `/auth/options` | — | `{registration_enabled}` |
| POST | `/forms/convert` | multipart: `file` (jeden plik), opcjonalnie `password` | `200` JSON formularza; nagłówek `X-Conversion-Warnings` |
| POST | `/forms/convert?report=true` | jak wyżej | `200 {form, report}` |
| POST | `/forms/validate` | JSON formularza | `200 {valid, errors[], warnings[]}` |
| GET | `/dictionaries` | — | słowniki predefiniowane i proponowane |
| GET | `/initial-data-sources` | — | źródła danych inicjalnych (PESEL, MLPZ) |
| GET | `/health/live` | — | `200`, proces działa |
| GET | `/health/ready` | — | `200` gotowe; 503, gdy model niedostępny |

Parametry `/forms/convert`: `report` (bool), `identitySource` (`PESEL` / `MLPZ`),
`model` (z `LLM_MODEL` / `LLM_MODELS`).

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=admin&password=$API_PASSWORD" | jq -r .access_token)

curl -s -X POST "http://localhost:8000/api/v1/forms/convert?report=true" \
  -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.docx" > wynik.json
```

**Raport** (`report=true`) zawiera m.in.: `sourceFile`, `extraction`, `llm`, `stats`,
`dictionaryProposals`, `warnings`, `fixes`, `confidence`, `review` (pola do sprawdzenia),
`timings`.

**Walidacja pliku** (pierwsze naruszenie kończy żądanie): jedno pole `file`; nazwa ≤ 250
znaków i bez `; : > < / \ | ' * % $`; rozmiar ≤ `MAX_FILE_SIZE_MB`; rozszerzenie z listy;
MIME z zawartości zgodny z rozszerzeniem; limity archiwów, stron i pikseli.

**Błędy** mają format RFC 9457 (`application/problem+json`) z polem `code`:

```json
{ "type": "https://coi-cf/errors/FILE_TOO_LARGE", "title": "Plik jest za duży",
  "status": 413, "code": "FILE_TOO_LARGE", "instance": "/api/v1/forms/convert", "request_id": "…" }
```

| Status | Kody |
|---|---|
| 400 | `MALFORMED_REQUEST`, `FILE_MISSING`, `TOO_MANY_FILES`, `FILENAME_TOO_LONG`, `FILENAME_FORBIDDEN_CHARS`, `FILE_EMPTY` |
| 401 / 403 | `NOT_AUTHENTICATED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS` / `FORBIDDEN`, `REGISTRATION_DISABLED` |
| 409 | `USERNAME_TAKEN` |
| 413 | `FILE_TOO_LARGE` |
| 415 | `UNSUPPORTED_EXTENSION`, `MIME_MISMATCH` |
| 422 | `ARCHIVE_TOO_LARGE`, `DOCUMENT_TOO_COMPLEX`, `DOCUMENT_UNREADABLE`, `DOCUMENT_PASSWORD_REQUIRED`, `DOCUMENT_PASSWORD_INVALID`, `VALIDATION_ERROR` |
| 429 / 503 / 504 | `TOO_MANY_REQUESTS` / `SERVER_BUSY`, `LLM_UNAVAILABLE`, `SERVICE_UNAVAILABLE` / `PROCESSING_TIMEOUT` |
| 500 | `INTERNAL_ERROR` |

## Testy

```bash
make test             # backend (pytest)
make test-frontend    # frontend
```
