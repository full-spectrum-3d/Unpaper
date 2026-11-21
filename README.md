# Cyfryzacja formularzy (HackNation 2026, zadanie COI)

Usługa REST, która przyjmuje blankiet formularza (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG)
i zwraca JSON z konfiguracją formularza gotową do importu w Generatorze Formularzy.
Działa w całości lokalnie: model językowy (Qwen3 8B, Apache-2.0) uruchamia Ollama
we własnym kontenerze, bez zewnętrznych API.

```
frontend (nginx, :8080) ──/api──▶ api (FastAPI, :8000) ──▶ llm (Ollama, tylko sieć wewnętrzna)
                                  walidacja → normalizacja (LibreOffice) → ekstrakcja (OCR)
                                  → analiza LLM → budowa formularza → weryfikacja
```

Szczegóły: `docs/specyfikacja-techniczna.md`, OpenAPI: `docs/openapi.json`.

## Wymagania

- Docker Engine 24+ z Docker Compose v2 (`docker compose version`).
- RAM: 16 GB (kontener `llm` z załadowanym qwen3:8b zajmuje ok. 6,5 GB).
- Dysk: ok. 12 GB (obrazy 6,4 GB, model 5,2 GB).
- CPU x86_64 (zalecane AVX2). Na samym CPU konwersja trwa zwykle 1,5–5 min. GPU NVIDIA jest
  opcjonalne (`docker-compose.gpu.yml`).
- Internet tylko przy budowie obrazów i jednorazowym pobraniu modelu. Z lokalnym modelem
  uruchomiona aplikacja nie łączy się z internetem (kontener `llm` jest w sieci `internal: true`).
  Model może też działać na zewnętrznym serwerze (sekcja *Lokalny model albo zewnętrzny serwer modelu*).

## Szybki start

```bash
make setup     # = docker compose build + scripts/init-env.sh + make model
make up        # docker compose up -d
```

Bez `make`:

```bash
docker compose build                                  # 1. obrazy
scripts/init-env.sh                                   # 2. .env z sekretami (wypisze hasło)
docker compose --profile setup run --rm llm-pull      # 3. model qwen3:8b (tylko z profilem ollama)
docker compose up -d                                  # 4. start
```

Po starcie:

| Adres | Co |
|---|---|
| http://localhost:8080 | aplikacja webowa (logowanie kontem z `.env`) |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/api/v1/health/ready | gotowość (200 = model dostępny) |

### Lokalny model albo zewnętrzny serwer modelu

Kontener `llm` (Ollama) i pobieranie modelu są opcjonalne. Steruje nimi profil Compose
`ollama`, włączony w `.env` zmienną `COMPOSE_PROFILES=ollama` (domyślnie).

| Tryb | `.env` | Co robi compose |
|---|---|---|
| lokalny model (domyślnie) | `COMPOSE_PROFILES=ollama`, `LLM_BASE_URL=http://llm:11434` | buduje i uruchamia `llm`, `make model` pobiera model |
| zewnętrzny serwer | `COMPOSE_PROFILES=` (pusto), `LLM_BASE_URL=https://…` | uruchamia tylko `api` i `frontend`; `make model` nic nie pobiera |

Serwer modelu na tym samym hoście: `LLM_BASE_URL=http://host.docker.internal:<port>`
(serwer musi nasłuchiwać na interfejsie dostępnym z Dockera, nie tylko na 127.0.0.1).
Gdy serwer jest niedostępny, `/health/ready` zwraca 503, a konwersja i tak zwraca
formularz zbudowany regułami (`W01_LLM_FALLBACK`).

Pierwsza konwersja po starcie może trwać dłużej o kilkadziesiąt sekund: model ładuje się
do pamięci (API rozgrzewa go przy starcie, `OLLAMA_KEEP_ALIVE=24h` trzyma go potem w RAM).

Zatrzymanie: `make down`. Logi: `docker compose logs -f api`.

## Budowanie obrazów

```bash
docker compose build              # wszystkie
docker compose build api          # tylko API
```

| Obraz | Bazowy (oficjalny, wersja + digest) | Użytkownik | Port |
|---|---|---|---|
| `coi-cf-api:0.1.0` | `python:3.14-alpine3.22` (multi-stage z `uv`) + Tesseract, LibreOffice, libmagic | `app` (10001) | 8000 |
| `coi-cf-frontend:0.1.0` | build `node:24-alpine3.22`, runtime `nginx:1.28-alpine3.23` | `nginx` (101) | 8080 |
| `coi-cf-llm:0.40.16` | `ollama/ollama:0.40.16` | `ollama` (10002) | 11434, tylko sieć wewnętrzna |

Samo API bez compose:

```bash
docker build -t coi-cf-api:0.1.0 backend
docker run --rm -p 8000:8000 --env-file .env -e LLM_BASE_URL=http://host.docker.internal:11434 \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true coi-cf-api:0.1.0
```

### Model offline

Na maszynie z internetem: `make model`, potem eksport wolumenu:

```bash
docker run --rm --user 0 -v ollama-models:/m -v "$PWD":/out --entrypoint tar \
  coi-cf-llm:0.40.16 -czf /out/ollama-models.tgz -C /m .
```

Na maszynie docelowej: `docker volume create ollama-models`, a następnie to samo polecenie
z `-xzf /out/ollama-models.tgz -C /m` i `chown -R 10002:10002 /m`.

## Uruchomienie i bezpieczeństwo kontenerów

Jak `docker-compose.yml` spełnia wymagania z treści zadania (pkt 5):

| Wymaganie | Realizacja |
|---|---|
| oficjalne obrazy bazowe, lekkie dystrybucje | `python`, `node`, `nginx` na Alpine; `ollama/ollama` (oficjalny obraz producenta, tylko Ubuntu) |
| jawne wersjonowanie, bez `latest` | każdy `FROM` z tagiem i `@sha256`, własne obrazy z wersją (`:0.1.0`) |
| proces na dedykowanym użytkowniku | `USER app` / `nginx` / `ollama`, żaden kontener nie działa jako root |
| tylko wymagane porty | na hoście 8000 (API) i 8080 (frontend); `llm` bez portu na hoście |
| sekrety tylko w runtime | `.env` (`env_file`) albo Docker secrets w `/run/secrets/<zmienna>`; obrazy nie zawierają sekretów, `.env` jest w `.gitignore` i `.dockerignore` |
| izolacja | `read_only: true`, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`, `pids_limit`; sieć `internal` bez internetu dla `llm` |
| pliki tylko tymczasowo | upload w pamięci / `tmpfs`, katalog per żądanie usuwany po odpowiedzi; brak wolumenów na dane użytkownika |

Porty na hoście zmienisz zmiennymi `API_PORT` i `FRONTEND_PORT` (np. `API_PORT=9000 docker compose up -d`).

Docker secrets zamiast `.env` (np. klucz RS256):

```yaml
services:
  api:
    secrets: [jwt_public_key]
secrets:
  jwt_public_key: { file: ./secrets/jwt_public.pem }
```

GPU NVIDIA (wymaga NVIDIA Container Toolkit):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## Konfiguracja

Wszystkie parametry to zmienne środowiskowe (pełna lista z opisami: `.env.example`,
specyfikacja §12). Aplikacja waliduje konfigurację przy starcie i nie uruchomi się
w trybie produkcyjnym bez sekretów.

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `MAX_FILE_SIZE_MB` | `20` | maksymalny rozmiar pliku (413 `FILE_TOO_LARGE`) |
| `MAX_UNCOMPRESSED_MB` / `MAX_PDF_PAGES` / `MAX_IMAGE_PIXELS` | `100` / `30` / `100000000` | limity ochronne (bomby ZIP, duże skany) |
| `MAX_CONCURRENT_JOBS` | `2` | równoległe konwersje |
| `REQUEST_TIMEOUT_S` | `540` | całkowity czas żądania (504 `PROCESSING_TIMEOUT`) |
| `AUTH_ENABLED` | `true` | `false` tylko z `APP_ENV=development` |
| `JWT_ALGORITHM` | `HS256` | `HS256` albo `RS256` |
| `JWT_SECRET` | — | sekret HS256, min. 32 bajty (generuje `scripts/init-env.sh`) |
| `JWT_PUBLIC_KEY` / `JWT_PRIVATE_KEY` | — | RS256; sam klucz publiczny = tylko weryfikacja tokenów z innego systemu |
| `JWT_ISSUER` / `JWT_AUDIENCE` / `JWT_EXPIRES_MIN` / `JWT_LEEWAY_S` | `coi-cf` / `coi-cf-api` / `60` / `30` | parametry tokenu |
| `JWT_SUBJECT_CLAIM` / `JWT_ROLES_CLAIM` / `JWT_REQUIRED_ROLE` | `sub` / `roles` / — | mapowanie claimów brokera tożsamości (np. Keycloak) |
| `API_USER` / `API_PASSWORD_HASH` | — | konto techniczne do `/auth/token`; hash argon2id: `make password-hash` |
| `CORS_ORIGINS` | `http://localhost:8080` | dozwolone originy |
| `COMPOSE_PROFILES` | `ollama` | `ollama` = lokalny kontener z modelem; pusto = zewnętrzny serwer pod `LLM_BASE_URL` |
| `LLM_BASE_URL` | `http://llm:11434` | adres serwera modelu (parametr integracyjny) |
| `LLM_MODEL` | `qwen3:8b` | model; po zmianie: `make model` |
| `LLM_TIMEOUT_S` / `LLM_NUM_CTX` | `240` / `8192` | limit wywołania modelu, okno kontekstu |
| `OCR_LANG` / `OCR_DPI` | `pol` / `300` | Tesseract |
| `CONVERTER_TIMEOUT_S` | `60` | LibreOffice (DOC, ODS) |
| `LOG_LEVEL` | `INFO` | logi bez treści dokumentów |

Zmiana hasła: `make password-hash`, wklej hash do `.env` w pojedynczych cudzysłowach,
`docker compose up -d api`.

## REST API

Prefiks `/api/v1`. Opis OpenAPI: `/docs`, `/openapi.json`, kopia w `docs/openapi.json`.
Wszystko poza `/auth/token` i `/health/*` wymaga nagłówka `Authorization: Bearer <JWT>`.

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/auth/token` | token JWT dla konta technicznego (`application/x-www-form-urlencoded`: `username`, `password`) → `{access_token, token_type, expires_in}` |
| POST | `/forms/convert` | **główny endpoint**: `multipart/form-data` z jednym polem `file` → JSON w formacie importu; nagłówek `X-Conversion-Warnings` z liczbą ostrzeżeń |
| POST | `/forms/convert?report=true` | `{form, report}`: raport z metodą ekstrakcji, czasami etapów, statystykami, ostrzeżeniami i propozycjami słowników |
| POST | `/forms/validate` | sprawdza dowolny JSON formularza (schemat + reguły) → `{valid, errors[], warnings[]}` |
| GET | `/dictionaries` | słowniki predefiniowane |
| GET | `/initial-data-sources` | źródła danych inicjalnych (PESEL, PESEL_ADDRESS, MLPZ) z atrybutami |
| GET | `/health/live` | proces działa |
| GET | `/health/ready` | 200 gotowe; 503, gdy LLM nieosiągalny |

Przykład:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token \
  -d "username=admin&password=$API_PASSWORD" | jq -r .access_token)

curl -s -X POST localhost:8000/api/v1/forms/convert \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@Wniosek o zwrot opłaty skarbowej.pdf" > wynik.json

curl -s -X POST localhost:8000/api/v1/forms/validate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @wynik.json
```

Walidacja pliku (kolejno, pierwsze naruszenie kończy żądanie):

| Sprawdzenie | Odpowiedź |
|---|---|
| dokładnie jedno pole `file` | 400 `FILE_MISSING` / `TOO_MANY_FILES` |
| nazwa ≤ 250 znaków, bez `; : > < / \ \| ' * % $` | 400 `FILENAME_TOO_LONG` / `FILENAME_FORBIDDEN_CHARS` |
| rozmiar ≤ `MAX_FILE_SIZE_MB` (liczony strumieniowo) | 413 `FILE_TOO_LARGE` |
| rozszerzenie z listy obsługiwanych | 415 `UNSUPPORTED_EXTENSION` |
| MIME z zawartości (libmagic) zgodny z rozszerzeniem | 415 `MIME_MISMATCH` |
| struktura i rozmiar archiwów, liczba stron i pikseli | 422 `ARCHIVE_TOO_LARGE` / `DOCUMENT_TOO_COMPLEX` |
| plik da się odczytać | 422 `DOCUMENT_UNREADABLE` / `DOCUMENT_PASSWORD_REQUIRED` |

Błędy mają format RFC 9457 (`application/problem+json`):

```json
{ "type": "https://coi-cf/errors/FILENAME_FORBIDDEN_CHARS", "title": "Niedozwolone znaki w nazwie pliku",
  "status": 400, "detail": "Nazwa pliku zawiera znak ':'", "code": "FILENAME_FORBIDDEN_CHARS" }
```

Gdy model jest niedostępny albo nie zdąży, API i tak zwraca poprawny formularz zbudowany
regułami z tekstu dokumentu (ostrzeżenia `W01_LLM_FALLBACK`, `W24_RULE_BASED_DRAFT`).

## Testy i rozwój

```bash
cd backend && uv sync && uv run pytest          # testy backendu
cd backend && uv run ruff check . && uv run mypy app
cd frontend && npm ci && npm test               # wymaga Node 24 (.nvmrc)
```

Lokalnie bez Dockera: `docker compose up -d llm` nie wystawia portu, więc do pracy nad API
uruchom Ollamę osobno (`docker run -d -p 127.0.0.1:11434:11434 -v ollama-models:/home/ollama/.ollama coi-cf-llm:0.40.16`)
i ustaw `LLM_BASE_URL=http://localhost:11434`, `APP_ENV=development`.

## Licencje

Wyłącznie oprogramowanie open source bez licencji copyleft wymagających ujawnienia kodu
aplikacji: FastAPI, pydantic, uvicorn (MIT/BSD), Angular (MIT), Ollama (MIT), Qwen3 (Apache-2.0),
Tesseract (Apache-2.0), nginx (BSD-2). LibreOffice (MPL-2.0, copyleft na poziomie pliku)
działa jako niezmodyfikowany osobny proces wywoływany z wiersza poleceń, więc nie obejmuje
kodu aplikacji. Lista zależności Pythona: `cd backend && uv run pip-licenses`.

## Rozwiązywanie problemów

- **`toomanyrequests` przy budowie**: limit pobrań z Docker Hub bez logowania. `docker login` albo odczekaj.
- **`/health/ready` zwraca 503**: model nie jest pobrany (`make model`) albo jeszcze się ładuje.
- **Wolumen modeli z wcześniejszej instalacji (root)**: `docker run --rm --user 0 -v ollama-models:/m --entrypoint chown coi-cf-llm:0.40.16 -R 10002:10002 /m`.
- **504 `PROCESSING_TIMEOUT`**: długi dokument na wolnym CPU. Zwiększ `REQUEST_TIMEOUT_S` (i `proxy_read_timeout` w `frontend/nginx.conf`) albo użyj GPU.
