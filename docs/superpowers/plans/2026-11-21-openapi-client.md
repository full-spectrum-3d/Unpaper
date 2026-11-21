# Klient API z OpenAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministyczny eksport `docs/openapi.json` z kodu backendu, wygenerowany klient Angulara (`ng-openapi-gen`) w `frontend/src/app/shared/api/` i skrypty `api:export` / `api:generate` / `api:check`, które wykrywają rozjazd kontraktu.

**Architecture:** Skrypt Pythona w `frontend/scripts/` importuje `create_app` z backendu i buduje go ze stałymi `Settings` (bez `.env`), uruchamiany przez `uv run --project ../backend`. `ng-openapi-gen` generuje modele + serwisy (Observable) z `docs/openapi.json`. Pliki wygenerowane są commitowane; `api:check` regeneruje i sprawdza `git status --porcelain` na obu ścieżkach.

**Tech Stack:** Python 3.14 + uv (backend), FastAPI `app.openapi()`, `ng-openapi-gen@^1.1.0` (peer: `@angular/core >=16`, `rxjs >=6.5`), Angular 22, npm scripts.

**Spec:** `docs/superpowers/specs/2026-11-21-openapi-client-design.md`

## Global Constraints

- Bez zmian w `backend/` (żadnych edycji plików backendu).
- Eksport nie czyta `.env` ani zmiennych środowiskowych: `Settings(_env_file=None, ...)` z wartościami stałymi. Żadnych prawdziwych sekretów w repo.
- `docs/openapi.json`: `json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`.
- Router `/auth` musi być w schemacie (HS256 + konto techniczne → `token_issuing_enabled`).
- `ng-openapi-gen.json`: `input: ../docs/openapi.json`, `output: src/app/shared/api`, `services: true`, `promises: false`, `ignoreUnusedModels: false`, `removeStaleFiles: true`.
- Pliki w `src/app/shared/api/` są commitowane, nieedytowane ręcznie, wyłączone z Prettiera.
- `provideApiConfiguration('')` w `app.config.ts` (ten sam origin; ścieżki w schemacie mają już `/api/v1`).
- Zależność dev z jawnym zakresem (`^1.1.0`), bez `latest`.
- Polecenia frontu po `source ~/.nvm/nvm.sh && nvm use`. Wymaga `uv` w PATH.
- Commity w Conventional Commits, bez linii `Co-Authored-By`.

## Review Focus

1. **Lokalny `.env` lub zmienne środowiskowe** nie mogą zmienić wyniku eksportu → krok `env does not leak into export` w Task 1.
2. **Dwa kolejne eksporty** dają identyczny plik (bez losowych soli, kolejności kluczy) → krok `export is deterministic` w Task 1.
3. **Nowy plik wygenerowany** (np. nowy model) musi być wykryty przez `api:check`, nie tylko zmiana istniejącego (`git diff` nie widzi plików nieśledzonych) → krok `check detects untracked generated file` w Task 3.
4. **Brak `uv`** daje czytelny błąd, a nie stack trace w środku npm → krok `missing uv fails clearly` w Task 1.
5. **Podwojony prefiks** `/api/v1/api/v1` w URL serwisu → krok `generated service path has single prefix` w Task 2.

---

### Task 1: Eksport `docs/openapi.json`

**Files:**
- Create: `frontend/scripts/export-openapi.py`
- Create: `docs/openapi.json` (wygenerowany)
- Modify: `frontend/package.json` (skrypt `api:export`)

**Interfaces:**
- Produces: `npm run api:export` → zapisuje `../docs/openapi.json` (ścieżka względem `frontend/`), kod 0 przy sukcesie.

- [ ] **Step 1: Implement `frontend/scripts/export-openapi.py`** – argument CLI: ścieżka wyjściowa. `Settings(_env_file=None, jwt_secret="openapi-export-" + "x" * 32, api_user="openapi", api_password_hash="$argon2id$v=19$m=65536,t=3,p=4$b3BlbmFwaQ$b3BlbmFwaQ")` (walidator sprawdza tylko prefiks `$argon2id$`; stała wartość = determinizm), `create_app(settings).openapi()`, zapis formatem z Global Constraints. Docstring: po co stałe ustawienia. Uwaga: `Settings` czyta też zmienne środowiskowe – skrypt przed konstrukcją usuwa z `os.environ` klucze pasujące do pól `Settings` (case-insensitive) albo przekazuje wszystkie istotne pola jawnie; wybierz pierwsze, jest pewniejsze.
- [ ] **Step 2: Add npm script** `"api:export": "command -v uv >/dev/null || { echo 'api:export wymaga uv (https://docs.astral.sh/uv/)' >&2; exit 1; }; uv run --project ../backend python scripts/export-openapi.py ../docs/openapi.json"`.
- [ ] **Step 3: Run** `npm run api:export` → kod 0, plik istnieje. Sprawdź: `python3 -c "import json;d=json.load(open('../docs/openapi.json'));p=d['paths'];assert '/api/v1/forms/convert' in p and '/api/v1/auth/token' in p, sorted(p)"`.
- [ ] **Step 4: export is deterministic** – `cp ../docs/openapi.json /tmp/a.json && npm run api:export && cmp /tmp/a.json ../docs/openapi.json` → brak różnic.
- [ ] **Step 5: env does not leak into export** – `JWT_ALGORITHM=RS256 AUTH_ENABLED=false APP_ENV=development npm run api:export && cmp /tmp/a.json ../docs/openapi.json` → brak różnic (bez wycieku `/auth` znika, więc cmp by się wysypał).
- [ ] **Step 6: missing uv fails clearly** – `PATH=/usr/bin:/bin npm run api:export` (z pełną ścieżką do npm/node, jeśli potrzeba) → kod ≠ 0 i komunikat `api:export wymaga uv`.
- [ ] **Step 7: Commit** `build(front): export OpenAPI schema from backend`

### Task 2: Generowany klient Angulara

**Files:**
- Create: `frontend/ng-openapi-gen.json`
- Create: `frontend/src/app/shared/api/**` (wygenerowane)
- Create/Modify: `frontend/.prettierignore` (dopisz `src/app/shared/api/`)
- Modify: `frontend/package.json` (devDependency `ng-openapi-gen@^1.1.0`, skrypt `api:generate`)
- Modify: `frontend/src/app/app.config.ts`

**Interfaces:**
- Consumes: `npm run api:export` (Task 1).
- Produces: `npm run api:generate` = `npm run api:export && ng-openapi-gen --config ng-openapi-gen.json`; `src/app/shared/api/api-configuration.ts` z `provideApiConfiguration`; serwisy per tag (`auth`, `forms`, `catalog`, `health`).

- [ ] **Step 1: Install** `npm install -D ng-openapi-gen@^1.1.0`.
- [ ] **Step 2: Write `ng-openapi-gen.json`** z wartościami z Global Constraints (+ `"$schema": "node_modules/ng-openapi-gen/ng-openapi-gen-schema.json"`, jeśli plik schematu istnieje w paczce).
- [ ] **Step 3: Add scripts** `api:generate`; dopisz `src/app/shared/api/` do `.prettierignore`.
- [ ] **Step 4: Run** `npm run api:generate` → w `src/app/shared/api/` są `api-configuration.ts`, `services/` (lub `services.ts`), `models/`.
- [ ] **Step 5: Wire config** – w `app.config.ts` dodaj `provideHttpClient()` (jeśli brak) i `provideApiConfiguration('')`.
- [ ] **Step 6: generated service path has single prefix** – `grep -rn "'/api/v1/forms/convert'" src/app/shared/api` znajduje ścieżkę dokładnie raz w postaci `/api/v1/forms/convert` (bez `/api/v1/api/v1`), a `api-configuration.ts` po `provideApiConfiguration('')` daje `rootUrl === ''`.
- [ ] **Step 7: Verify build** `npx ng build` → sukces bez błędów TS; `npm run test:storybook` → wszystkie testy jak dotąd (19/19).
- [ ] **Step 8: Commit** `feat(front): generate Angular API client from OpenAPI`

### Task 3: `api:check` i dokumentacja

**Files:**
- Modify: `frontend/package.json` (skrypt `api:check`)
- Modify: `frontend/README.md` (sekcja „Klient API”)

**Interfaces:**
- Consumes: `npm run api:generate` (Task 2).
- Produces: `npm run api:check` – kod 0, gdy repo zgodne z backendem; ≠ 0 i lista plików, gdy nie.

- [ ] **Step 1: Add script** `"api:check": "npm run api:generate && git diff --exit-code --stat -- ../docs/openapi.json src/app/shared/api && test -z \"$(git status --porcelain -- ../docs/openapi.json src/app/shared/api)\" || { echo 'Kontrakt API nieaktualny: uruchom npm run api:generate i zacommituj zmiany' >&2; exit 1; }"` (dopasuj grupowanie, żeby komunikat wypisywał się tylko przy błędzie).
- [ ] **Step 2: clean repo passes** – po zacommitowaniu Task 2: `npm run api:check` → kod 0.
- [ ] **Step 3: check detects stale committed client** – symuluj nieaktualny klient: dopisz linię do jednego wygenerowanego pliku i zacommituj tymczasowo (`git commit -am tmp`). `npm run api:check` → generator przywraca plik, diff względem HEAD ≠ pusty → kod ≠ 0 i komunikat. Cofnij: `git reset --hard HEAD~1`.
- [ ] **Step 4: check detects untracked generated file** – usuń z indeksu jeden plik modelu/serwisu przez tymczasowy commit `git rm --cached <plik> && git commit -m tmp`, `npm run api:check` → ≠ 0 (plik pojawia się jako nieśledzony); cofnij `git reset --hard HEAD~1`.
- [ ] **Step 5: Write README section** „Klient API”: po zmianie backendu `npm run api:generate` i commit `docs/openapi.json` + `src/app/shared/api/`; `npm run api:check` przed PR; nie edytować plików w `shared/api/`; wymaga `uv`.
- [ ] **Step 6: Commit** `build(front): add API contract check and docs`
