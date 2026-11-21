# Cyfryzacja formularzy – automatyczna konwersja blankietów na formularze e-usług

HackNation 2026, wyzwanie Centralnego Ośrodka Informatyki „Cyfryzacja formularzy”.

## Opis projektu

Urzędy publikują formularze jako PDF, dokumenty Word i arkusze albo skany. Przeniesienie
każdego z nich do e-usługi wymaga ręcznej analizy: trzeba rozpoznać pola, pogrupować je
w strony tematyczne, dobrać typy i walidacje, słowniki oraz zależności między polami.

Ta aplikacja robi to automatycznie. Urzędnik wgrywa blankiet (PDF, DOC, DOCX, ODS, XLSX,
JPG, JPEG, PNG), a usługa REST zwraca JSON z konfiguracją formularza gotową do importu
w Generatorze Formularzy COI. Wynik:

- ma strukturę zgodną z plikami wzorcowymi (`konfiguracja_form_*.json`) i schematem importu,
- spełnia standardy projektowania formularzy: strony tematyczne, sekcje predefiniowane
  (dane wnioskodawcy, adres, kontakt, załączniki, zgody), strona końcowa,
- łączy pola ze słownikami (TERYT, Kraje…) i danymi inicjalnymi (PESEL, MLPZ),
- zawiera zależności dynamiczne (JSONata w `states`) i walidatory (PESEL, NIP, REGON, kod pocztowy, e-mail…),
- przechodzi weryfikację strukturalną z autonaprawą, zanim trafi do użytkownika.

Zasada działania: **AI rozumie, kod buduje**. Lokalny model językowy (Qwen3 8B, Apache-2.0,
uruchamiany przez Ollama) tylko odczytuje z dokumentu, jakie dane są potrzebne. Gotowy
JSON składa deterministyczny kod według reguł z materiałów COI, więc wynik jest zawsze
poprawny strukturalnie, także gdy model jest niedostępny (wtedy szkic powstaje z reguł).
Rozwiązanie nie korzysta z żadnych zewnętrznych API, a pliki istnieją tylko w pamięci
i katalogu tymczasowym na czas żądania.

Do usługi dołączona jest aplikacja webowa: import wielu plików naraz, podgląd
wygenerowanego formularza tak, jak zobaczy go obywatel (z walidacją pól i zależnościami
między nimi), podgląd i pobranie JSON-a.

## Spis treści

1. [Zgodność z wymaganiami](#zgodność-z-wymaganiami)
2. [Architektura](#architektura)
3. [Wymagania sprzętowe i programowe](#wymagania-sprzętowe-i-programowe)
4. [Budowanie obrazów Docker](#budowanie-obrazów-docker)
5. [Uruchomienie aplikacji](#uruchomienie-aplikacji)
6. [Konfiguracja](#konfiguracja)
7. [REST API](#rest-api)
8. [Bezpieczeństwo kontenerów](#bezpieczeństwo-kontenerów)
9. [Testy](#testy)
10. [Licencje](#licencje)
11. [Rozwiązywanie problemów](#rozwiązywanie-problemów)
12. [Struktura repozytorium](#struktura-repozytorium)

## Zgodność z wymaganiami

### Zakres obowiązkowy (pkt 3.2 i 5 zadania)

| Wymaganie | Realizacja |
|---|---|
| REST API przyjmujące pojedynczy plik formularza | `POST /api/v1/forms/convert`, dokładnie jedno pole `file` ([REST API](#rest-api)) |
| Formaty PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | ekstrakcja tekstu i układu: pdfplumber (PDF), python-docx, openpyxl; DOC i ODS przez LibreOffice; skany przez Tesseract OCR |
| JSON zgodny ze strukturą oczekiwaną przez aplikację | budowa według wzorców i schematu, weryfikacja JSON Schema + reguły R01–R15 przed odpowiedzią |
| JSON zgodny ze standardami projektowania | strony tematyczne, sekcje predefiniowane, strona `FINISH`, obligatoryjność pól, limit sekcji na stronę |
| Walidacja typu pliku z weryfikacją MIME | rozszerzenie + MIME z zawartości (libmagic) + struktura archiwów; 415 przy niezgodności |
| Nazwa pliku ≤ 250 znaków, bez `; : > < / \ \| ' * % $` | 400 `FILENAME_TOO_LONG` / `FILENAME_FORBIDDEN_CHARS` |
| Konfigurowalny maksymalny rozmiar pliku | `MAX_FILE_SIZE_MB`, liczony strumieniowo (413) |
| Tylko tymczasowe przetwarzanie plików | upload w RAM do `SPOOL_MAX_MB`, potem `tmpfs`; katalog per żądanie usuwany po odpowiedzi; brak bazy i wolumenów na dane |
| Kompletna konfiguracja Docker, izolowane środowisko | `docker-compose.yml` z trzema usługami ([Bezpieczeństwo kontenerów](#bezpieczeństwo-kontenerów)) |
| Wymagania dla obrazów Docker | oficjalne obrazy, Alpine, wersje z digestem, bez `latest`, użytkownicy bez roota, tylko potrzebne porty, sekrety w runtime |
| Konfiguracja: rozmiar pliku, JWT, parametry integracyjne | zmienne środowiskowe ([Konfiguracja](#konfiguracja)) |
| Open source bez copyleftu, bez licencji komercyjnych, bez zewnętrznych API i SaaS | [Licencje](#licencje): biblioteki aplikacji na licencjach permisywnych, obraz `llm` bez bibliotek NVIDIA; model lokalny w sieci `internal` bez internetu, funkcje chmurowe Ollamy wyłączone (`OLLAMA_NO_CLOUD`) |
| Python 3.14 | backend: Python 3.14, FastAPI |
| Dokumentacja architektury | [Architektura](#architektura), `docs/specyfikacja-techniczna.md`, `docs/architecture/` |
| README: budowanie, uruchomienie, konfiguracja, REST API | ten plik |

### Rozszerzenia opcjonalne (pkt 3.3 zadania)

| Rozszerzenie | Realizacja |
|---|---|
| I. Słowniki i dane inicjalne | pola adresu, kraju, numerów kierunkowych dostają `dictionaryName` z bazy słowników; dane wnioskodawcy `defaultValueType: EXTERNAL_SYSTEM` z PESEL / MLPZ (`GET /dictionaries`, `GET /initial-data-sources`) |
| II. Propozycje nowych słowników | listy zamknięte bez słownika w bazie (np. rodzaj podatku) trafiają jako propozycja do raportu konwersji (`report.dictionaryProposals`) |
| III. Zależności pól, sekcji i stron | warunki „pokaż, gdy…” jako zapytania JSONata w `states` (`SHOW`, `READ_ONLY`), przepływ stron w `flow.links` |
| IV. Frontend do ładowania plików i przeglądania JSON | aplikacja Angular na :8080: logowanie, przeciąganie wielu plików, kolejka ze statusami, pytanie o hasło dokumentu chronionego hasłem, podgląd i pobranie JSON |
| V. Wizualizacja formularza e-usługi | podgląd formularza z JSON-a w aplikacji webowej: strony, sekcje, pola z podpowiedziami, słowniki z kaskadą TERYT, stany `SHOW` i `READ_ONLY` liczone z warunków JSONata, oznaczenie pól z rejestru |
| VI. Walidacja danych i UX | w JSON-ie walidatory dobrane do pól (`PESEL`, `NIP`, `REGON`, `ZIP_CODE`, `EMAIL`, `EPUAP`, `ADE`, `SERIAL_NUMBER_ID_CARD`) i obligatoryjność (`REQUIRED`); podgląd sprawdza te walidatory, pokazuje błędy przy polach i blokuje „Dalej” na stronie z błędami; import wsadowy (batch) z pobraniem wszystkich wyników jako ZIP; `POST /forms/validate` |

## Architektura

```
┌──────────────────────┐      ┌─────────────────────────────┐      ┌───────────────────────┐
│ frontend (nginx)     │      │ api (FastAPI, Python 3.14)  │      │ llm (Ollama)          │
│ Angular SPA          │─────▶│ [1] walidacja pliku         │─────▶│ Qwen3 8B (Apache-2.0) │
│ :8080                │ /api │ [2] normalizacja (LibreOff.)│ HTTP │ :11434 tylko w sieci  │
└──────────────────────┘      │ [3] ekstrakcja (tekst, OCR) │      │ wewnętrznej           │
                              │ [4] analiza AI → szkic      │      └───────────────────────┘
                              │ [5] budowa formularza       │
                              │ [6] weryfikacja, autonaprawa│
                              │ :8000, tmpfs /tmp           │
                              └─────────────────────────────┘
```

| Etap | Co robi |
|---|---|
| [1] walidacja | nazwa, rozmiar (strumieniowo), rozszerzenie, MIME z zawartości, struktura i rozmiar archiwów, liczba stron i pikseli |
| [2] normalizacja | DOC → DOCX i ODS → XLSX przez LibreOffice (osobny proces z timeoutem), odszyfrowanie plików z hasłem |
| [3] ekstrakcja | wspólny model dokumentu (`DocumentModel`): bloki tekstu, tabele, ramki, wykropkowania; OCR Tesseract dla skanów |
| [4] analiza AI | model dostaje tekst dokumentu jako dane i zwraca szkic (`FormDraft`) w schemacie structured output; poprawki i reguły w kodzie; przy błędzie lub braku modelu szkic z reguł |
| [5] budowa | deterministyczny kod: sekcje predefiniowane, typy pól, walidatory, słowniki, dane inicjalne, `states`, układ, `flow` |
| [6] weryfikacja | JSON Schema i reguły R01–R15 z autonaprawą; gdy błędy zostają, formularz zastępczy |

API działa samodzielnie i spełnia cały zakres obowiązkowy; frontend jest dodatkiem.
Brak bazy danych: słowniki, katalog danych inicjalnych i szablony sekcji są plikami
zasobów w obrazie API.

Dokumentacja szczegółowa:

- `docs/specyfikacja-techniczna.md` – specyfikacja: pipeline, API, format JSON, reguły budowy, bezpieczeństwo, decyzje wobec rozbieżności w materiałach (§7.4),
- `docs/architecture/` – architektura, wdrożenie z Węzłem Krajowym (`wezel-krajowy.md`),
- `docs/superpowers/specs/` – projekty modułów (ekstrakcja, LLM, uwierzytelnianie, frontend),
- `docs/openapi.json` – opis REST API (OpenAPI 3.1).

## Wymagania sprzętowe i programowe

- Docker Engine 24+ z Docker Compose v2.20+ (`docker compose version`).
- RAM: 16 GB (kontener `llm` z załadowanym qwen3:8b zajmuje ok. 6,5 GB).
- Dysk: ok. 7 GB (obrazy 1,5 GB, model 5,2 GB); przy budowie obrazu `llm` Docker pobiera
  dodatkowo obraz producenta Ollamy (5,1 GB, tylko etap budowania – można go potem usunąć).
- CPU x86_64 (zalecane AVX2). Na samym CPU konwersja trwa zwykle 1,5–5 min.
  GPU NVIDIA jest opcjonalne (`docker-compose.gpu.yml`).
- Internet tylko przy budowie obrazów i jednorazowym pobraniu modelu. Z lokalnym modelem
  uruchomiona aplikacja nie łączy się z internetem.
- Do generowania `.env` skryptem: powłoka POSIX (`sh`). `make` jest opcjonalny.

## Budowanie obrazów Docker

```bash
docker compose build              # wszystkie obrazy aktywnych usług
docker compose build api          # tylko API
```

Albo bez compose, pojedynczo:

```bash
docker build -t coi-cf-api:0.1.0 backend
docker build -t coi-cf-frontend:0.1.0 frontend
docker build -t coi-cf-llm:0.40.16 llm
```

| Obraz | Dockerfile | Obraz bazowy (oficjalny, tag + digest) | Użytkownik | Port |
|---|---|---|---|---|
| `coi-cf-api:0.1.0` | `backend/Dockerfile` | `python:3.14-alpine3.22`, multi-stage: builder z `uv`, runtime z Tesseract, LibreOffice, libmagic | `app` (10001) | 8000 |
| `coi-cf-frontend:0.1.0` | `frontend/Dockerfile` | build `node:24-alpine3.22`, runtime `nginx:1.28-alpine3.23` | `nginx` (101) | 8080 |
| `coi-cf-llm:0.40.16` | `llm/Dockerfile` (target `cpu`) | `ubuntu:24.04` + binarka i biblioteki CPU z `ollama/ollama:0.40.16`, bez bibliotek NVIDIA (161 MB) | `ollama` (10002) | 11434 (tylko sieć wewnętrzna) |
| `coi-cf-llm:0.40.16-gpu` | `llm/Dockerfile` (target `gpu`) | `ollama/ollama:0.40.16` z CUDA; tylko z `docker-compose.gpu.yml` | `ollama` (10002) | jw. |

Obrazy nie zawierają sekretów ani modelu. Model trafia do wolumenu `ollama-models`
przy instalacji ([Uruchomienie](#uruchomienie-aplikacji), krok 3).

## Uruchomienie aplikacji

### Szybki start

```bash
make setup     # obrazy + .env z sekretami + pobranie modelu
make up        # start w tle
```

### Krok po kroku (bez make)

```bash
docker compose build                                  # 1. obrazy
scripts/init-env.sh                                   # 2. .env: losowy JWT_SECRET, konto admin, hasło
docker compose --profile setup run --rm llm-pull      # 3. model qwen3:8b do wolumenu (jednorazowo)
docker compose up -d                                  # 4. start
```

`scripts/init-env.sh` wypisuje wygenerowane hasło konta `admin` jeden raz. Własny login
i hasło: `API_PASSWORD='…' scripts/init-env.sh nazwa_uzytkownika`. Ręcznie: skopiuj
`.env.example` do `.env` i uzupełnij `JWT_SECRET`, `API_USER`, `API_PASSWORD_HASH`
(hash: `make password-hash`).

### Po starcie

| Adres | Co |
|---|---|
| http://localhost:8080 | aplikacja webowa (logowanie kontem z `.env`) |
| http://localhost:8000/docs | Swagger UI z opisem API |
| http://localhost:8000/api/v1/health/ready | gotowość: 200 = model dostępny |

```bash
docker compose ps                 # stan usług (healthy)
docker compose logs -f api        # logi API (JSON, bez treści dokumentów)
make down                         # zatrzymanie (docker compose down)
```

Pierwsza konwersja po starcie może trwać dłużej o kilkadziesiąt sekund: model ładuje się
do pamięci. API rozgrzewa go przy starcie, a `OLLAMA_KEEP_ALIVE=24h` trzyma go potem w RAM.

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
formularz zbudowany regułami (ostrzeżenie `W01_LLM_FALLBACK`).

### Model offline

Na maszynie z internetem `make model`, potem eksport wolumenu:

```bash
docker run --rm --user 0 -v ollama-models:/m -v "$PWD":/out --entrypoint tar \
  coi-cf-llm:0.40.16 -czf /out/ollama-models.tgz -C /m .
```

Na maszynie docelowej:

```bash
docker volume create ollama-models
docker run --rm --user 0 -v ollama-models:/m -v "$PWD":/out --entrypoint sh coi-cf-llm:0.40.16 \
  -c 'tar -xzf /out/ollama-models.tgz -C /m && chown -R 10002:10002 /m'
```

### GPU NVIDIA

Domyślny obraz `llm` działa tylko na CPU i nie zawiera bibliotek NVIDIA. Nakładka GPU
buduje target `gpu`: obraz producenta Ollamy z CUDA i cuDNN. Te biblioteki są bezpłatne,
ale na licencji własnościowej NVIDIA, a nie open source (patrz [Licencje](#licencje)).
Wymaga NVIDIA Container Toolkit na hoście:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Samo API bez compose

```bash
docker run --rm -p 8000:8000 --env-file .env \
  -e LLM_BASE_URL=http://host.docker.internal:11434 --add-host host.docker.internal:host-gateway \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
  coi-cf-api:0.1.0
```

`docker run --env-file` nie usuwa cudzysłowów, więc w pliku dla `docker run` hash
`API_PASSWORD_HASH` wpisz bez nich (compose cudzysłowy usuwa i ich wymaga przy znakach `$`).

## Konfiguracja

Wszystkie parametry to zmienne środowiskowe (pydantic-settings). Compose przekazuje
je do API z pliku `.env` (`env_file`); wzór z komentarzami: `.env.example`. Zmienna
ustawiona w środowisku ma pierwszeństwo przed plikiem. Sekrety można też podać jako
Docker secrets: plik `/run/secrets/<nazwa_zmiennej_małymi_literami>`, np.
`/run/secrets/jwt_private_key`.

API sprawdza konfigurację przy starcie. W trybie produkcyjnym nie uruchomi się bez
sekretów JWT i konta technicznego ani z `AUTH_ENABLED=false`.

### Plik i limity przetwarzania

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `MAX_FILE_SIZE_MB` | `20` | **maksymalny rozmiar pliku**; większy → 413 `FILE_TOO_LARGE` |
| `MAX_UNCOMPRESSED_MB` | `100` | limit rozmiaru po dekompresji DOCX / XLSX / ODS (ochrona przed bombami ZIP) |
| `MAX_PDF_PAGES` | `30` | maksymalna liczba stron PDF |
| `MAX_IMAGE_PIXELS` | `100000000` | maksymalna liczba pikseli obrazu (długie skany wielostronicowe) |
| `SPOOL_MAX_MB` | `10` | do tego rozmiaru upload jest w RAM, powyżej w `tmpfs` |
| `MAX_CONCURRENT_JOBS` | `2` | równoległe konwersje; kolejne żądania czekają |
| `REQUEST_TIMEOUT_S` | `540` | całkowity czas żądania łącznie z czekaniem w kolejce; po nim 504 |

### Uwierzytelnianie JWT

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `AUTH_ENABLED` | `true` | `false` dozwolone tylko z `APP_ENV=development` |
| `JWT_ALGORITHM` | `HS256` | `HS256` (wspólny sekret) albo `RS256` (para kluczy) |
| `JWT_SECRET` | — | sekret HS256, min. 32 bajty; wymagany dla HS256 |
| `JWT_PUBLIC_KEY` | — | klucz publiczny PEM dla RS256 (w jednej linii z `\n` albo jako Docker secret) |
| `JWT_PRIVATE_KEY` | — | klucz prywatny RS256; bez niego API tylko weryfikuje tokeny wydane przez inny system, a `/auth/token` jest wyłączony |
| `JWT_ISSUER` | `coi-cf` | wymagany `iss` |
| `JWT_AUDIENCE` | `coi-cf-api` | wymagany `aud` |
| `JWT_EXPIRES_MIN` | `60` | ważność tokenu (1–1440 min) |
| `JWT_LEEWAY_S` | `30` | tolerancja różnicy zegarów przy `exp` / `nbf` / `iat` |
| `JWT_SUBJECT_CLAIM` | `sub` | claim z identyfikatorem użytkownika (np. `preferred_username`) |
| `JWT_ROLES_CLAIM` | `roles` | claim z rolami; kropka = zagnieżdżenie (np. `realm_access.roles` w Keycloak) |
| `JWT_REQUIRED_ROLE` | — | rola wymagana do użycia API; pusta = bez wymogu, brak roli → 403 |
| `API_USER` | — | login konta technicznego dla `/auth/token` |
| `API_PASSWORD_HASH` | — | hash argon2id hasła (`make password-hash`); w `.env` w pojedynczych cudzysłowach |

### Integracja z modelem AI

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `COMPOSE_PROFILES` | `ollama` | `ollama` = lokalny kontener z modelem; pusto = zewnętrzny serwer pod `LLM_BASE_URL` (zmienna Compose, nie API) |
| `LLM_BASE_URL` | `http://llm:11434` | adres serwera modelu (API Ollama) |
| `LLM_MODEL` | `qwen3:8b` | nazwa modelu; po zmianie `make model` |
| `LLM_TIMEOUT_S` | `240` | limit jednego wywołania modelu; po nim szkic z reguł |
| `LLM_TEMPERATURE` | `0` | temperatura (0 = powtarzalne wyniki) |
| `LLM_SEED` | `42` | ziarno losowania |
| `LLM_NUM_CTX` | `8192` | okno kontekstu modelu w tokenach |

### Ekstrakcja i budowa formularza

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `OCR_LANG` | `pol` | język Tesseract |
| `OCR_DPI` | `300` | rozdzielczość renderowania skanów PDF do OCR |
| `CONVERTER_TIMEOUT_S` | `60` | limit konwersji LibreOffice (DOC, ODS) |
| `INITIAL_DATA_IDENTITY_SOURCE` | `MLPZ` | źródło danych „Twoje dane”: `MLPZ` albo `PESEL` |
| `FINISH_PAGE_STYLE` | `sample` | strona końcowa jak we wzorcach (`sample`) albo `info_section` |
| `MAX_SECTIONS_PER_PAGE` | `8` | powyżej tej liczby sekcji przedmiot wniosku dzielony jest na kolejne strony |
| `RODO_CLAUSE_URL` | — | adres klauzuli informacyjnej RODO (np. w BIP) linkowanej w sekcji zgód; bez niego zgoda jest zwykłym tekstem bez linku, a raport konwersji ma ostrzeżenie `W28_RODO_CLAUSE_URL_MISSING` |

### Aplikacja i HTTP

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `APP_ENV` | `production` | `production` albo `development` |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`; logi JSON na stdout, bez treści dokumentów |
| `CORS_ORIGINS` | `http://localhost:8080` | dozwolone originy, rozdzielone przecinkami |
| `API_PORT` / `FRONTEND_PORT` | `8000` / `8080` | porty na hoście (zmienne Compose) |

Zmiana hasła: `make password-hash`, wklej hash do `.env` i wykonaj `docker compose up -d api`.

## REST API

- Prefiks: `/api/v1`.
- Opis OpenAPI: http://localhost:8000/docs (Swagger UI), `/openapi.json`, kopia w `docs/openapi.json`.
- Uwierzytelnianie: nagłówek `Authorization: Bearer <JWT>` na wszystkich endpointach poza `/auth/token` i `/health/*`.
- Każda odpowiedź ma nagłówek `X-Request-ID` (można go też podać w żądaniu); ten sam identyfikator jest w logach.

### Endpointy

| Metoda | Ścieżka | Wejście | Odpowiedź |
|---|---|---|---|
| POST | `/auth/token` | `application/x-www-form-urlencoded`: `username`, `password` | `200 {access_token, token_type: "bearer", expires_in}`; 401 przy złych danych |
| POST | `/forms/convert` | `multipart/form-data`: `file` (dokładnie jeden plik), opcjonalnie `password` dla dokumentu z hasłem | `200` JSON w formacie importu; nagłówek `X-Conversion-Warnings: <liczba>` |
| POST | `/forms/convert?report=true` | jak wyżej | `200 {form, report}` |
| POST | `/forms/convert?identitySource=PESEL` | jak wyżej; opcjonalny parametr query `identitySource` (`PESEL` albo `MLPZ`) wybiera źródło imienia, nazwiska i PESEL w sekcji „Twoje dane”; brak = `INITIAL_DATA_IDENTITY_SOURCE`; inna wartość: 422 `VALIDATION_ERROR` | jak wyżej |
| POST | `/forms/validate` | `application/json`: JSON formularza | `200 {valid, errors[], warnings[]}` (bez autonaprawy) |
| GET | `/dictionaries` | — | słowniki: predefiniowane (`PREDEFINED`) i proponowane (`PROPOSED`) |
| GET | `/initial-data-sources` | — | źródła danych inicjalnych (`PESEL`, `PESEL_ADDRESS`, `MLPZ`) z atrybutami i referencją do `defaultValue` |
| GET | `/health/live` | — | `200 {status: "ok"}`, proces działa |
| GET | `/health/ready` | — | `200 {status: "ok"}` gotowe; 503 `LLM_UNAVAILABLE`, gdy model nieosiągalny |

### Przykład

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=admin&password=$API_PASSWORD" | jq -r .access_token)

# konwersja: wynik gotowy do importu
curl -s -X POST http://localhost:8000/api/v1/forms/convert \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@Wniosek o zwrot opłaty skarbowej.pdf" > wynik.json

# konwersja z raportem
curl -s -X POST "http://localhost:8000/api/v1/forms/convert?report=true" \
  -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.docx" | jq .report.warnings

# walidacja JSON-a (np. poprawionego ręcznie)
curl -s -X POST http://localhost:8000/api/v1/forms/validate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @wynik.json
```

Konwersja na CPU trwa zwykle 1,5–5 minut; klient HTTP nie powinien przerywać żądania
wcześniej niż po `REQUEST_TIMEOUT_S`.

### Wynik konwersji

Domyślnie odpowiedź to sam JSON formularza, bez opakowania, gotowy do importu
(struktura z `OpisImportowanegoPlikuJSON` i wzorców `konfiguracja_form_*.json`):

```
{
  "title": "Wniosek o …",
  "tabs": [                                   strony; ostatnia ma type "FINISH"
    { "id": "<uuid>", "title": "…", "type": "MAIN",
      "questions": [                          na poziomie strony tylko SECTION / REPEATING_SECTION
        { "x": 0, "y": 0, "rows": 4, "cols": 3,
          "field": { "id": "<uuid>", "type": "SECTION", "techName": "…", "title": "…",
                     "repeatingSectionGrid": [ … pola sekcji … ],
                     "validation": [], "states": [], "options": [], … } } ] } ],
  "flow": { "links": [ { "id": "<uuid>", "source": "<tab id>", "target": "<tab id>" } ] }
}
```

Pole w sekcji ma m.in. `type` (`TEXT_FIELD`, `SELECT`, `RADIO`, `CHECKBOX`, `DATEPICKER`,
`NUMBER`, `TEXTAREA`, `FILE_UPLOADER`…), `validation` (`REQUIRED`, `PESEL`, `NIP`, `ZIP_CODE`…),
`dictionaryName`, `defaultValue` + `defaultValueType: "EXTERNAL_SYSTEM"` dla danych
inicjalnych oraz `states` z zapytaniami JSONata (`SHOW`, `READ_ONLY`).

Raport (`report=true`):

| Klucz | Zawartość |
|---|---|
| `sourceFile` | nazwa, MIME, rozmiar, liczba stron, czy plik był odszyfrowany |
| `extraction` | metoda (`pdf_text`, `ocr`, `docx`, `xlsx`), konwersja LibreOffice, średnia pewność OCR, liczba bloków |
| `llm` | model, czas, ponowienia, czy użyto szkicu z reguł i dlaczego, liczba tokenów |
| `stats` | liczba stron, sekcji, pól i warunków `states` |
| `dictionaryProposals` | propozycje nowych słowników z pozycjami i polami, które ich używają |
| `warnings` | ostrzeżenia `{code, message, path?}`: miejsca do sprawdzenia przez urzędnika |
| `fixes` | poprawki wprowadzone przez autonaprawę |
| `timings`, `durationMs` | czasy etapów i całości w ms |

Najczęstsze ostrzeżenia: `W01_LLM_FALLBACK` i `W24_RULE_BASED_DRAFT` (szkic z reguł,
bez modelu), `W12_LOW_OCR_CONFIDENCE` (słaba jakość skanu), `W13_FIELD_NOT_IN_DOCUMENT`
(pole, którego etykiety nie ma w dokumencie), `W27_FORM_REBUILT` (formularz zastępczy), `W28_RODO_CLAUSE_URL_MISSING` (zgoda RODO bez linku:
ustaw `RODO_CLAUSE_URL`).

### Walidacja pliku

Sprawdzenia w tej kolejności; pierwsze naruszenie kończy żądanie:

| # | Sprawdzenie | Odpowiedź |
|---|---|---|
| 1 | dokładnie jedno pole `file` | 400 `FILE_MISSING` / `TOO_MANY_FILES` |
| 2 | nazwa ≤ 250 znaków | 400 `FILENAME_TOO_LONG` |
| 3 | nazwa bez `; : > < / \ \| ' * % $` | 400 `FILENAME_FORBIDDEN_CHARS` |
| 4 | rozmiar ≤ `MAX_FILE_SIZE_MB` (liczony strumieniowo), plik niepusty | 413 `FILE_TOO_LARGE` / 400 `FILE_EMPTY` |
| 5 | rozszerzenie: pdf, doc, docx, ods, xlsx, jpg, jpeg, png (bez względu na wielkość liter) | 415 `UNSUPPORTED_EXTENSION` |
| 6 | MIME z zawartości pliku (libmagic) zgodny z rozszerzeniem; nagłówek `Content-Type` klienta jest ignorowany | 415 `MIME_MISMATCH` |
| 7 | archiwa DOCX / XLSX / ODS: oczekiwane wpisy, rozmiar po dekompresji ≤ `MAX_UNCOMPRESSED_MB` | 415 `MIME_MISMATCH` / 422 `ARCHIVE_TOO_LARGE` |
| 8 | obraz ≤ `MAX_IMAGE_PIXELS`, PDF ≤ `MAX_PDF_PAGES` stron | 422 `DOCUMENT_TOO_COMPLEX` |
| 9 | plik da się otworzyć | 422 `DOCUMENT_UNREADABLE` / `DOCUMENT_PASSWORD_REQUIRED` / `DOCUMENT_PASSWORD_INVALID` |

### Błędy

Format RFC 9457 (`application/problem+json`), pole `code` do obsługi w kliencie:

```json
{ "type": "https://coi-cf/errors/FILENAME_FORBIDDEN_CHARS", "title": "Niedozwolone znaki w nazwie pliku",
  "status": 400, "detail": "Nazwa pliku zawiera znak ':'", "code": "FILENAME_FORBIDDEN_CHARS",
  "instance": "/api/v1/forms/convert", "request_id": "…" }
```

| Status | Kody |
|---|---|
| 400 | `MALFORMED_REQUEST`, `FILE_MISSING`, `TOO_MANY_FILES`, `FILENAME_TOO_LONG`, `FILENAME_FORBIDDEN_CHARS`, `FILE_EMPTY` |
| 401 | `NOT_AUTHENTICATED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS` |
| 403 | `FORBIDDEN` (brak roli `JWT_REQUIRED_ROLE`) |
| 413 | `FILE_TOO_LARGE` |
| 415 | `UNSUPPORTED_EXTENSION`, `MIME_MISMATCH` |
| 422 | `ARCHIVE_TOO_LARGE`, `DOCUMENT_TOO_COMPLEX`, `DOCUMENT_UNREADABLE`, `DOCUMENT_PASSWORD_REQUIRED`, `DOCUMENT_PASSWORD_INVALID`, `VALIDATION_ERROR` |
| 503 | `LLM_UNAVAILABLE` (tylko `/health/ready`; konwersja przechodzi wtedy na szkic z reguł) |
| 504 | `PROCESSING_TIMEOUT` (przekroczony `REQUEST_TIMEOUT_S`) |
| 500 | `INTERNAL_ERROR` (bez szczegółów w treści; pełny log z `request_id` po stronie serwera) |

## Bezpieczeństwo kontenerów

| Wymaganie (pkt 5 zadania) | Realizacja |
|---|---|
| oficjalne obrazy bazowe | `python`, `node`, `nginx`, `ubuntu` (Docker Official Images); z oficjalnego obrazu `ollama/ollama` kopiujemy tylko binarkę i biblioteki CPU |
| lekkie dystrybucje | Alpine dla API i frontendu; `llm` na `ubuntu:24.04` (161 MB), bo binarka Ollamy wymaga glibc |
| jawne wersjonowanie, bez `latest` | każdy `FROM` z tagiem i `@sha256`; własne obrazy z wersją (`:0.1.0`), wersja `uv` też przypięta |
| dedykowany użytkownik z ograniczonymi uprawnieniami | `USER app` / `nginx` / `ollama`; żaden kontener nie działa jako root |
| tylko wymagane porty | na hoście 8000 (API) i 8080 (frontend); `llm` bez portu na hoście |
| sekrety tylko w runtime | `.env` (`env_file`) albo Docker secrets; żadnych `ARG`/`ENV` z sekretami; `.env` w `.gitignore` i `.dockerignore` |
| izolowane środowisko | `read_only: true`, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`, `pids_limit`; `llm` w sieci `internal: true` bez internetu i z `OLLAMA_NO_CLOUD=1`; model pobiera osobny jednorazowy kontener (`llm-pull`) |

Dodatkowo: nagłówki bezpieczeństwa w nginx (CSP, `X-Content-Type-Options`,
`Referrer-Policy`, `frame-ancestors 'none'`), `init: true` w API (sprzątanie procesów
LibreOffice), XML z dokumentów parsowany przez `defusedxml`, treść dokumentu trafia
do modelu tylko jako dane, a wynik modelu jest ograniczony schematem i weryfikowany.

Docker secrets zamiast `.env`, np. dla RS256:

```yaml
services:
  api:
    secrets: [jwt_public_key]
secrets:
  jwt_public_key: { file: ./secrets/jwt_public.pem }
```

## Testy

```bash
cd backend && uv sync && uv run pytest            # testy jednostkowe, API, golden
cd backend && uv run ruff check . && uv run mypy app
cd frontend && npm ci && npm test                 # wymaga Node 24 (.nvmrc)
```

Testy na materiałach konkursowych: `COI_MATERIALS_DIR=/ścieżka/do/Wnioski uv run pytest tests/extraction`.
Ocena jakości analizy AI na zestawie wzorcowym: `backend/llm_eval/`.

Praca nad API bez Dockera: uruchom Ollamę z portem na hoście
(`docker run -d -p 127.0.0.1:11434:11434 -v ollama-models:/home/ollama/.ollama coi-cf-llm:0.40.16`),
ustaw w `.env` `APP_ENV=development`, `LLM_BASE_URL=http://localhost:11434` i uruchom
`cd backend && uv run uvicorn app.main:create_app --factory --reload`.

## Licencje

Domyślna konfiguracja (CPU) składa się wyłącznie z oprogramowania open source, bez
licencji komercyjnych. Biblioteki i frameworki, z którymi łączy się kod aplikacji, mają
licencje permisywne; żadna nie wymaga ujawnienia kodu aplikacji. Licencje sprawdzone
w metadanych pakietów zainstalowanych w obrazach.

Biblioteki i frameworki aplikacji:

| Komponent | Licencja |
|---|---|
| Backend: FastAPI, Starlette, pydantic, uvicorn, httpx, PyJWT, argon2-cffi, cryptography, jsonschema, jsonata-python, defusedxml (52 pakiety w obrazie) | MIT, BSD, Apache-2.0, PSF – lista: `cd backend && uv run pip-licenses` |
| Ekstrakcja: pdfplumber, pdfminer.six, pypdfium2 (PDFium), python-docx, openpyxl, lxml, Pillow, pytesseract, python-magic, msoffcrypto-tool, olefile | MIT, BSD-3-Clause, Apache-2.0, MIT-CMU |
| Biblioteki natywne dołączone do pakietów (libjpeg, libpng, libtiff, openjpeg, harfbuzz, ICU…) | permisywne; freetype na wybranej licencji FTL; libgcc/libstdc++ z wyjątkiem GCC Runtime Library Exception |
| Frontend w przeglądarce: Angular, NgRx, RxJS, fflate, jsonata, tslib | MIT, Apache-2.0, 0BSD |
| Fonty Open Sans, JetBrains Mono (`@fontsource`) | SIL OFL-1.1 (licencja fontu, nie obejmuje kodu aplikacji) |

Programy uruchamiane jako osobne procesy lub usługi:

| Komponent | Licencja |
|---|---|
| Ollama, llama.cpp / ggml | MIT |
| Model Qwen3 8B | Apache-2.0 |
| Tesseract OCR + dane `pol`, `osd`; Leptonica | Apache-2.0; BSD-2-Clause |
| libmagic (`file`) | BSD-2-Clause |
| nginx | BSD-2-Clause |
| LibreOffice | MPL-2.0 |

Uwagi:

- **LibreOffice** (konwersja DOC i ODS) to niezmodyfikowany program wywoływany z wiersza
  poleceń w osobnym procesie. Słaby copyleft MPL-2.0 dotyczy tylko jego własnych plików.
  Pakiet `libreoffice-common` w Alpine wymaga też bibliotek systemowych na LGPL/GPL
  (m.in. Qt6, GTK, GStreamer). Nie są one linkowane z kodem aplikacji, więc ich licencje
  go nie obejmują. Format DOC wymaga konwertera, a nie ma alternatywy o licencji
  permisywnej, która by go obsługiwała.
- **certifi** (MPL-2.0, zależność `httpx`) to niezmodyfikowany zbiór certyfikatów CA.
- **Pakiety systemowe** obrazów bazowych (busybox i apk-tools w Alpine, coreutils
  w Ubuntu) mają licencje GPL, jak w każdym obrazie tych dystrybucji. Są to osobne
  programy systemu, nie biblioteki aplikacji.
- **Narzędzia budowania frontendu** (lightningcss i axe-core na MPL-2.0, dane caniuse-lite
  na CC-BY-4.0) działają tylko przy budowie i nie trafiają do obrazu.
- **Opcjonalny obraz GPU** (`docker-compose.gpu.yml`) zawiera biblioteki NVIDIA CUDA
  i cuDNN: bezpłatne, ale na licencji własnościowej NVIDIA. Domyślny obraz `llm` ich nie
  ma – Ollama działa w nim wyłącznie na CPU.

## Rozwiązywanie problemów

| Objaw | Rozwiązanie |
|---|---|
| `toomanyrequests` przy budowie | limit pobrań z Docker Hub bez logowania: `docker login` albo odczekaj |
| `/health/ready` zwraca 503 | model nie jest pobrany (`make model`) albo jeszcze się ładuje; sprawdź `docker compose logs llm` |
| API nie startuje, błąd konfiguracji w logu | brak `JWT_SECRET` / `API_USER` / `API_PASSWORD_HASH` w `.env` – `scripts/init-env.sh` |
| hash hasła w `.env` „ucięty” | hash musi być w pojedynczych cudzysłowach (znaki `$`) |
| wolumen modeli z wcześniejszej instalacji (właściciel root) | `docker run --rm --user 0 -v ollama-models:/m --entrypoint chown coi-cf-llm:0.40.16 -R 10002:10002 /m` |
| 504 `PROCESSING_TIMEOUT` | długi dokument na wolnym CPU: zwiększ `REQUEST_TIMEOUT_S` i `LLM_TIMEOUT_S` (oraz `proxy_read_timeout` w `frontend/nginx.conf`) albo użyj GPU |
| wynik z ostrzeżeniem `W01_LLM_FALLBACK` | model nie odpowiedział w `LLM_TIMEOUT_S`; formularz zbudowany regułami – zwiększ limit albo użyj GPU |

## Struktura repozytorium

```
backend/              API (FastAPI): app/api, app/pipeline (etapy 1–6), app/resources, testy, llm_eval
frontend/             aplikacja Angular + nginx.conf
llm/                  obraz Ollama z użytkownikiem bez roota, skrypt pobrania modelu
docs/                 specyfikacja, architektura, openapi.json, projekty modułów
scripts/init-env.sh   generowanie .env z sekretami
wymagania/            materiały konkursowe COI
docker-compose.yml    usługi api, frontend, llm (+ llm-pull)
docker-compose.gpu.yml  nakładka GPU
.env.example          wzór konfiguracji
Makefile              setup, build, model, up, down, logs, test, password-hash
```
