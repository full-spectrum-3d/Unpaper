# Uwierzytelnianie i warstwa `core` – projekt

| | |
|---|---|
| Data | 2026-11-21 |
| Zakres | `backend/app/core/{config,security,errors}.py`, `backend/app/api/v1/auth.py`, podpięcie w `main.py` |
| Podstawa | specyfikacja §6.1, §6.4, §10.1, §10.4, §12; treść zadania §5 |

## 1. Cel

Zabezpieczyć REST API tokenami JWT tak, żeby:
- spełnić wymóg zadania „konfigurowalne parametry uwierzytelniania JWT”;
- działać w pełni offline na obronie (`docker compose up`, bez żadnego dostawcy tożsamości);
- dać się wpiąć w infrastrukturę COI bez zmian w kodzie – tylko konfiguracją (potencjał wdrożeniowy, 20% oceny).

`core` ustala przy okazji wzorce dla całego backendu: jedna klasa konfiguracji (§12) i jeden format błędów (RFC 9457).

## 2. Cele, nie-cele, anty-cele

**Cele**
- `POST /api/v1/auth/token` dla jednego konta technicznego z konfiguracji.
- Weryfikacja tokenu na wszystkich endpointach poza `/auth/token` i `/health/*`.
- HS256 (domyślnie) i RS256, w tym RS256 tylko do weryfikacji (tokeny wydaje inny system).
- Walidacja konfiguracji przy starcie – aplikacja nie wstaje z błędną lub niebezpieczną konfiguracją.
- Wszystkie błędy API jako `application/problem+json`.

**Nie-cele**
- Wielu użytkowników, role, uprawnienia.
- Refresh tokeny, unieważnianie tokenów (blacklist), wylogowanie po stronie serwera.
- Pobieranie kluczy z sieci (JWKS, OIDC discovery).
- Rate limiting logowania (ewentualnie w nginx, poza tym projektem).
- Zmiany we frontendzie, endpoint `/auth/me`.

**Anty-cele** (porażka, nawet jeśli „działa”)
- Jakiekolwiek wywołanie sieciowe w ścieżce uwierzytelniania – łamałoby zakaz zależności od zewnętrznych usług.
- Sekret, hasło lub klucz w obrazie Docker, w repo albo w logach.
- Akceptowanie algorytmu wskazanego w nagłówku tokenu (`alg=none`, pomylenie HS256/RS256).
- Konieczność konfiguracji czegokolwiek poza `.env`, żeby jury uruchomiło rozwiązanie.

## 3. Ograniczenia

- Biblioteki: PyJWT (MIT) z `cryptography` (Apache-2.0/BSD) dla RS256, `argon2-cffi` (MIT), pydantic-settings (MIT). **Bez passlib** (nierozwijany) – zmiana względem spec §10.1.
- Sekrety tylko w runtime: zmienne środowiskowe albo Docker secrets (`/run/secrets/*`). Kontener ma `read_only: true`.
- Python 3.14, mypy strict, ruff.

## 4. Rozważone podejścia

| Podejście | Wady / zalety | Decyzja |
|---|---|---|
| A. Tylko HS256, własne tokeny | Najprościej; w COI byłaby to osobna wyspa logowania | odrzucone jako jedyny tryb |
| C. Osobny tryb `AUTH_MODE=external` z kluczami z JWKS | Dobre pod wdrożenie, ale pobieranie JWKS to zależność sieciowa od zewnętrznej usługi – ryzyko przy ocenie | odrzucone |
| **A + RS256 tylko do weryfikacji** | Ten sam efekt co C bez nowego pojęcia: gdy skonfigurowany jest wyłącznie klucz publiczny, API tylko weryfikuje tokeny, wydawane przez dowolny system z kluczem prywatnym. Brak ruchu sieciowego | **wybrane** |

## 5. Projekt

### 5.1. Tryby wynikające z konfiguracji

| Konfiguracja | Wydawanie (`/auth/token`) | Weryfikacja |
|---|---|---|
| `JWT_ALGORITHM=HS256` + `JWT_SECRET` (domyślnie) | tak | `JWT_SECRET` |
| `RS256` + `JWT_PRIVATE_KEY` + `JWT_PUBLIC_KEY` | tak | `JWT_PUBLIC_KEY` |
| `RS256` + tylko `JWT_PUBLIC_KEY` | **nie** – trasa nie jest rejestrowana (404, brak w OpenAPI) | `JWT_PUBLIC_KEY` |
| `AUTH_ENABLED=false` (tylko `APP_ENV=development`) | nie | wyłączona, każde żądanie jako podmiot `dev` |

### 5.2. `core/config.py`

- Jedna klasa `Settings(BaseSettings)` z **wszystkimi** zmiennymi z §12 (nie tylko auth), z typami i ograniczeniami (`PositiveInt`, `Literal`, `SecretStr` dla sekretów).
- `secrets_dir="/run/secrets"`, ale tylko gdy katalog istnieje. Klucz PEM można więc podać jako Docker secret (`/run/secrets/jwt_private_key`) zamiast wieloliniowej zmiennej.
- Nowa zmienna `JWT_LEEWAY_S` (domyślnie `30`) – tolerancja różnicy zegarów dla `exp`/`nbf`/`iat`.
- `model_validator` (fail fast przy starcie):
  1. `APP_ENV=production` i `AUTH_ENABLED=false` → błąd.
  2. HS256 → `JWT_SECRET` wymagany, min. 32 bajty (RFC 7518 §3.2).
  3. RS256 → `JWT_PUBLIC_KEY` wymagany. Klucze parsowane przez `cryptography` już przy starcie; jeśli jest też prywatny, sprawdzamy, że tworzy parę z publicznym.
  4. Wydawanie włączone (HS256 albo RS256 z kluczem prywatnym) i `AUTH_ENABLED=true` → wymagane `API_USER` i `API_PASSWORD_HASH`; hash musi zaczynać się od `$argon2id$`.
- Właściwość `token_issuing_enabled` (wynik reguł z 5.1).
- `get_settings()` z `lru_cache` jako zależność FastAPI; w testach podmieniana przez `app.dependency_overrides`.

### 5.3. `core/security.py`

- **Hasło:** `argon2.PasswordHasher().verify`. Login porównywany `hmac.compare_digest`. Przy złym loginie i tak wykonujemy weryfikację na stałym, sztucznym hashu, żeby czas odpowiedzi nie zdradzał, czy login istnieje.
- **Wydanie tokenu** `create_access_token(subject) -> (token, expires_in)`: claimy `sub`, `iss`, `aud`, `iat`, `nbf`, `exp`, `jti` (UUID4). Algorytm i klucz wyłącznie z `Settings`.
- **Weryfikacja** `decode_access_token(token) -> TokenClaims`: `jwt.decode(..., algorithms=[settings.jwt_algorithm], issuer=..., audience=..., leeway=..., options={"require": ["exp", "iat", "iss", "aud", "sub"]})`. Lista algorytmów ma zawsze jeden element z konfiguracji – chroni przed `alg=none` i pomyleniem HS256/RS256.
- **Zależność FastAPI** `require_auth` na bazie `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)` → zwraca `Principal(subject)`. Daje przycisk „Authorize” w Swagger UI. Przy `AUTH_ENABLED=false` zwraca `Principal("dev")`.
- **Narzędzie CLI:** `python -m app.core.security hash-password` (hasło przez `getpass`, nie z argumentu) → wypisuje hash argon2id. Cel `make password-hash`.

### 5.3a. Mapowanie claimów i wymagana rola (dodane 2026-11-21)

Cel: proste podpięcie pod broker tożsamości przed Węzłem Krajowym (`docs/architecture/wezel-krajowy.md`).

- `JWT_SUBJECT_CLAIM` (domyślnie `sub`) – claim z identyfikatorem użytkownika; `sub` nie jest już na liście wymaganych claimów PyJWT, sprawdzamy wskazany claim (brak → 401 `INVALID_TOKEN`).
- `JWT_ROLES_CLAIM` (domyślnie `roles`) – claim z rolami; ścieżka z kropkami dla zagnieżdżeń (`realm_access.roles`). Role jako lista napisów albo napis rozdzielony spacjami.
- `JWT_REQUIRED_ROLE` (domyślnie brak) – gdy ustawiona, token bez tej roli → **403 `FORBIDDEN`** z `WWW-Authenticate: Bearer error="insufficient_scope"`.
- Walidacja przy starcie: ścieżki nie mogą wskazywać claimów rejestrowanych (`iss`, `aud`, `exp`, `iat`, `nbf`, `jti`) ani się pokrywać.
- Własne tokeny (`/auth/token`) zapisują identyfikator i rolę pod skonfigurowanymi ścieżkami, więc przechodzą tę samą weryfikację co tokeny brokera.
- `Principal` ma pole `roles`.

### 5.4. `core/errors.py`

- `ProblemDetail` (Pydantic): `type`, `title`, `status`, `detail`, `code`, `instance`, `request_id`; dla 422 dodatkowo `errors[]`.
- `AppError(Exception)` z polami `code`, `status`, `title`, `detail`, `headers`. Kody w jednym `StrEnum` `ErrorCode` z przypisanym statusem i polskim tytułem. Kody z §6.3 (walidacja pliku) też trafią tutaj – reszta zespołu tylko dopisuje pozycje.
- `type` = `https://coi-cf/errors/<CODE>` (jak w spec §6.4).
- Handlery rejestrowane przez `install_error_handlers(app)`:
  - `AppError` → problem+json;
  - `RequestValidationError` → 422 `VALIDATION_ERROR` z listą błędów;
  - `StarletteHTTPException` (404, 405…) → problem+json;
  - `Exception` → 500 `INTERNAL_ERROR` bez szczegółów; pełny wyjątek do logu z `request_id`.
- Middleware `request_id`: przyjmuje `X-Request-ID` od klienta (jeśli poprawny UUID) albo generuje nowy; zwraca go w nagłówku odpowiedzi.

Kody związane z uwierzytelnianiem:

| Kod | Status | Kiedy | Nagłówek |
|---|---|---|---|
| `NOT_AUTHENTICATED` | 401 | brak tokenu | `WWW-Authenticate: Bearer` |
| `INVALID_TOKEN` | 401 | zły podpis, wygasły, zły `iss`/`aud`, brak claimów | `WWW-Authenticate: Bearer error="invalid_token"` |
| `INVALID_CREDENTIALS` | 401 | zły login lub hasło przy `/auth/token` | – |

`detail` nie rozróżnia przyczyn (wygasły vs zły podpis); przyczyna trafia tylko do logu.

### 5.5. `api/v1/auth.py`

- `POST /auth/token`, `OAuth2PasswordRequestForm` (`username`, `password`, `application/x-www-form-urlencoded`).
- Odpowiedź `TokenResponse {access_token, token_type: "bearer", expires_in}` z nagłówkiem `Cache-Control: no-store` (RFC 6749 §5.1).
- Rejestrowany tylko przy `token_issuing_enabled`.

### 5.6. `main.py`

- `create_app(settings: Settings | None = None)` – fabryka aplikacji (uvicorn `--factory`); ustawienia trzymane w `app.state.settings`, zależność `get_settings` czyta je z żądania. Brak globalnego `app = create_app()`, więc import modułu nie wymaga sekretów.
- Routery publiczne: `auth`, `health`. Chronione: `forms`, `catalog` – `include_router(..., dependencies=[Depends(require_auth)])`. Każdy nowy router domyślnie trafia do grupy chronionej.
- `install_error_handlers`, middleware `request_id`, CORS z `CORS_ORIGINS`.

### 5.7. Testy

Poza zakresem tej zmiany (decyzja zespołu, 2026-11-21). Weryfikacja ręczna: start aplikacji z różnymi konfiguracjami, logowanie i wywołanie chronionego endpointu przez Swagger UI / curl.

### 5.8. Zmiany w pozostałych plikach

- `pyproject.toml`: `pyjwt[crypto]` zamiast `pyjwt`.
- `.env.example`: `JWT_LEEWAY_S`; hash w pojedynczych cudzysłowach (`API_PASSWORD_HASH='$argon2id$...'`) – docker compose nie interpoluje wtedy `$`; komentarz o kluczach RS256 przez Docker secrets.
- `Makefile`: cel `password-hash`.
- Specyfikacja: §10.1 – usunąć passlib, dopisać RS256 tylko do weryfikacji i `JWT_LEEWAY_S`; §12 – nowa zmienna; §14 – pytanie Q10.

## 6. Otwarte pytanie (mentorzy COI)

**Q10:** Czy weryfikacja tokenów RS256 wydanych przez system COI (klucz publiczny w konfiguracji) jest pożądana? Do czasu odpowiedzi domyślny HS256 spełnia wymagania samodzielnie.

## 7. Zostawione wykonawcy

- Polskie brzmienie tytułów błędów.
- Format logów (szczegóły logowania JSON to osobne zadanie; tu tylko `request_id` i brak sekretów w logach).
- Parametry kosztu argon2 – domyślne z `argon2-cffi`.
