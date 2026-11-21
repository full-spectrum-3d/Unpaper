# Klient API z OpenAPI we froncie

Data: 2026-11-21 · Rozmiar: mała zmiana (krótki design)

## Cel
Kontrakt REST między backendem (FastAPI) a frontendem (Angular) nie może się rozjechać po cichu. Front korzysta z modeli i serwisów wygenerowanych ze schematu OpenAPI backendu, a nie z ręcznie pisanych typów. Zmiana w backendzie wychodzi po regeneracji jako błąd kompilacji TypeScriptu albo diff w gicie.

## Cele / poza zakresem / anty-cele
- Cele: eksport `docs/openapi.json` z kodu backendu (spec §14), generowanie klienta Angulara do `frontend/src/app/shared/api/`, skrypty npm do regeneracji i do sprawdzania rozjazdu, podpięcie `ApiConfiguration` w `app.config.ts`.
- Poza zakresem: zmiany w kodzie backendu (`response_model`, modele endpointów) – robi to zespół backendu. Interceptory auth/błędów, store NgRx, CI (repo nie ma pipeline'u).
- Anty-cele: ręczne edycje plików wygenerowanych; schemat zależny od lokalnego `.env` (różny plik na różnych maszynach); prawdziwe sekrety w eksporcie.

## Podejścia
- 1. `openapi-typescript` – same typy, wywołania na `HttpClient` piszemy sami. Odrzucone przez użytkownika.
- **2. `ng-openapi-gen`** (wybrane przez użytkownika) – generowane modele i serwisy Angulara per tag. Więcej wygenerowanego kodu, ale gotowe metody wywołań.
- 3. `@hey-api/openapi-ts` – własny klient fetch obok `HttpClient`. Odrzucone, bo omija interceptory Angulara.

## Decyzje użytkownika
- Zostajemy po stronie frontu, bez zmian w backendzie.
- `openapi.json` generujemy sami przy każdej aktualizacji projektu (nie czekamy, aż dostarczy go backend).
- Generator: `ng-openapi-gen`.

## Projekt
- **Eksport schematu:** skrypt `frontend/scripts/export-openapi.py` uruchamiany przez `uv run --project ../backend`. Buduje `create_app(Settings(...))` z **jawnie podanymi, stałymi ustawieniami** (bez czytania `.env`, sztuczny `jwt_secret` ≥ 32 bajty i konto techniczne, żeby router `/auth` był w schemacie) i zapisuje `docs/openapi.json` (posortowane klucze, wcięcie 2, końcowy znak nowej linii), żeby plik był deterministyczny.
- **Generacja:** `ng-openapi-gen` (devDependency, wersja przypięta zakresem) z plikiem `frontend/ng-openapi-gen.json`: `input: ../docs/openapi.json`, `output: src/app/shared/api`, `services: true`, `promises: false` (Observable pod efekty NgRx), `ignoreUnusedModels: false`, `removeStaleFiles: true`.
- **Skrypty npm:**
  - `api:export` – eksport schematu,
  - `api:generate` – `api:export` + generacja klienta,
  - `api:check` – `api:generate`, potem `git diff --exit-code -- ../docs/openapi.json src/app/shared/api`: niezerowy kod, gdy zacommitowany klient nie odpowiada backendowi.
- **Pliki wygenerowane są commitowane** (dzięki temu `api:check` ma z czym porównać, a front buduje się bez Pythona) i wyłączone z Prettiera (`.prettierignore`).
- **Konfiguracja:** `provideApiConfiguration('')` w `app.config.ts`, czyli ten sam origin (w Dockerze nginx kieruje `/api` do backendu). Ścieżki w schemacie FastAPI już zawierają prefiks `/api/v1`, więc root URL go nie powtarza.
- **Dokumentacja:** krótka sekcja w `frontend/README.md`: kiedy uruchomić `npm run api:generate` i że plików z `shared/api/` się nie edytuje.

## Zostawione wykonawcy
- Dokładna wersja `ng-openapi-gen` zgodna z Angularem 22.
- Minimalne dane `Settings` potrzebne, żeby `create_app` przeszło walidację (np. format `api_password_hash`).
- Test dymny: build (`ng build`) przechodzi z wygenerowanym klientem.

## Ryzyka
- Dopóki endpointy backendu zwracają `dict[str, object]`, wygenerowane typy odpowiedzi są luźne (`{ [key: string]: unknown }`); modele (`FormDefinition` itd.) pojawią się w schemacie dopiero, gdy backend użyje ich w endpointach.
- `api:export` wymaga `uv` i zależności backendu (Python 3.14) na maszynie, która regeneruje klienta.
