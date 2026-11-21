# CoiCfFrontend

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 22.3.0.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.

## Klient API

Klient HTTP w `src/app/shared/api/` jest generowany ze schematu OpenAPI backendu (`docs/openapi.json` w katalogu głównym repo, czyli `../docs/openapi.json` z `frontend/`).

- Po każdej zmianie API backendu uruchom `npm run api:generate` i zacommituj obie ścieżki: `docs/openapi.json` oraz `src/app/shared/api/`.
- Przed otwarciem PR uruchom `npm run api:check`. Skrypt kończy się błędem, gdy zacommitowany schemat lub klient odbiega od backendu (także o nowe, niezacommitowane pliki).
- Nie edytuj ręcznie plików w `src/app/shared/api/` i nie umieszczaj tam własnych: `removeStaleFiles: true` usuwa je przy każdym generowaniu.
- Wymagane jest narzędzie [`uv`](https://docs.astral.sh/uv/), którym eksportowany jest schemat z backendu; `uv` instaluje przy tym środowisko Pythona 3.14 backendu.
- Wygenerowany `FormsService` nie wyśle jeszcze pliku do `/forms/convert` (endpoint backendu to stub bez ciała żądania), a typy odpowiedzi są luźne, dopóki backend nie zadeklaruje `response_model`. Nie obchodź tego ręcznymi wywołaniami `HttpClient`; zregeneruj klienta, gdy backend to doda (`api:check` to wykaże).
