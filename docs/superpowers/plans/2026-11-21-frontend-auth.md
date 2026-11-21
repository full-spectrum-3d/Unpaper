# Logowanie we froncie (auth) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ekran `/login`, slice `auth` w NgRx z kopią w `sessionStorage`, automatyczne wylogowanie, interceptory auth/błędów, guardy, powłoka z topbarem i pole `app-text-field`.

**Architecture:** Slice `auth` (akcje, reducer, selektory, meta-reducer `sessionStorage`, efekty) zarejestrowany na root w `app.config.ts`. Funkcyjne interceptory i guardy w `core/`. Wywołanie `/auth/token` wyłącznie przez wygenerowany `AuthService`. Ekran logowania na Signal Forms (`form()`, `required`, `FormField`) z polem `app-text-field` implementującym `FormValueControl` (`value = model('')`).

**Tech Stack:** Angular 22 (standalone, signals, Signal Forms z `@angular/forms/signals`), NgRx 22 (`@ngrx/store`, `@ngrx/effects`, `@ngrx/store-devtools`), Vitest przez `ng test` (`@angular/build:unit-test`, jsdom), Storybook 10 (play testy, a11y `error`), Tailwind 4 z tokenami.

**Spec:** `docs/superpowers/specs/2026-11-21-frontend-auth-design.md` (czytaj sekcję „Rozstrzygnięcia po przeglądzie wykonawcy” – wiąże).

## Global Constraints

- Token tylko w store i `sessionStorage` (klucz `coi-cf.auth`, wartość `{"token","expiresAt","username"}`); nigdy `localStorage`, cookies ani URL. Hasło nigdy w stanie, `sessionStorage` ani logach.
- `Authorization: Bearer` tylko dla URL zaczynających się od `/api/`, nigdy dla `/api/v1/auth/token` ani innych hostów.
- `returnUrl` akceptowany tylko, gdy zaczyna się od `/` i nie od `//`; inaczej `/import`.
- Komunikaty (dokładnie): `INVALID_CREDENTIALS` → „Nieprawidłowy login lub hasło”; `NOT_AUTHENTICATED`/`INVALID_TOKEN` → „Sesja wygasła, zaloguj się ponownie”; `FORBIDDEN` → „Brak uprawnień”; `VALIDATION_ERROR` → „Uzupełnij login i hasło”; status 0 → „Brak połączenia z serwerem”; 404 na `/api/v1/auth/token` → „Logowanie hasłem jest wyłączone w tej konfiguracji”; inaczej `detail` z problem+json albo „Wystąpił nieoczekiwany błąd” (+ ` (kod zgłoszenia: <X-Request-ID>)`, jeśli nagłówek jest).
- Komunikat sesji na ekranie logowania: „Sesja wygasła, zaloguj się ponownie”.
- Nazwa aplikacji: „Cyfryzacja formularzy”; fallback nazwy użytkownika: „konto techniczne”.
- Angular: standalone, `input()`/`output()`/`model()`, bez jawnego `OnPush`, `inject()`. Tylko klasy semantyczne Tailwind, `focus-ring` na elementach interaktywnych.
- Testy: unit `npx ng test --watch=false`, Storybook `npm run test:storybook` – oba zielone na końcu każdego zadania.
- Commity w Conventional Commits, bez linii `Co-Authored-By`. Bez nowych zależności.

## Review Focus

1. **Uszkodzony / obcy wpis w `sessionStorage`** (np. `"{"`, brak pól, `sessionStorage` rzuca) – aplikacja startuje wylogowana zamiast się wysypać → test `ignores corrupted storage entry` w Task 2.
2. **Złośliwy `returnUrl`** (`//evil.com`, `https://evil.com`) – po zalogowaniu ląduje na `/import` → test `rejects external returnUrl` w Task 4.
3. **Kilka równoczesnych 401** – jedna nawigacja, brak „Sesja wygasła” po ręcznym wylogowaniu → testy `logout is idempotent` (Task 2) i `unauthorized after manual logout does nothing` (Task 4).
4. **Uśpiona karta z przeterminowanym tokenem** – guard wpuszcza tylko, gdy `expiresAt > Date.now()` → test `guard rejects expired token` w Task 4.
5. **Hasło w DevTools** – akcja `login` zmaskowana w `actionSanitizer` → test `sanitizer masks password` w Task 5.

---

### Task 1: `app-text-field`

**Files:**
- Create: `frontend/src/app/shared/ui/text-field/text-field.ts`, `text-field.stories.ts`

**Interfaces:**
- Produces: `TextField` (selector `app-text-field`, implements `FormValueControl<string>` z `@angular/forms/signals`): `value = model('')`, `label = input.required<string>()`, `type = input<'text' | 'password'>('text')`, `description = input<string>()`, `error = input<string>()`, `autocomplete = input<string>()`. Unikalne `id` per instancja (licznik modułowy), `<label for>`, `aria-describedby` = id opisu i/lub błędu, `aria-invalid="true"` gdy `error`.

- [ ] **Step 1: Write failing stories** (`UI/TextField`, wzorzec jak `shared/ui/button/button.stories.ts`): harness z polami `Login` (z opisem „Konto techniczne”), `Hasło` (`type="password"`), `Z błędem` (`error="Pole wymagane"`).

```ts
const login = c.getByLabelText('Login');
expect(login).toHaveAccessibleDescription('Konto techniczne');
await userEvent.type(login, 'dev');
expect(login).toHaveValue('dev');
expect(c.getByLabelText('Hasło')).toHaveAttribute('type', 'password');
const bad = c.getByLabelText('Z błędem');
expect(bad).toHaveAttribute('aria-invalid', 'true');
expect(bad).toHaveAccessibleDescription(/Pole wymagane/);
expect(getComputedStyle(bad).borderColor).not.toBe(getComputedStyle(login).borderColor);
await userEvent.tab(); // fokus widoczny
expect(getComputedStyle(document.activeElement as HTMLElement).outlineWidth).toBe('3px');
```
Plus story `Preview` z `globals: { theme: 'preview' }` (a11y w obu motywach) i story `SignalForm`: harness z `form(signal({ login: '' }))` i `<app-text-field label="Login" [formField]="f.login" />`; po `userEvent.type(…, 'abc')` → `f.login().value()` (wypisany w `<output data-testid="v">`) to `abc`.
- [ ] **Step 2: Run** `npm run test:storybook` → FAIL (brak modułu).
- [ ] **Step 3: Implement `TextField`.** Klasy: input `block w-full bg-surface text-fg border border-border-input rounded-field px-field-x py-field-y text-body focus-ring`, przy błędzie `border-danger`; etykieta `text-label font-semibold`, opis `text-fg-muted`, błąd `text-danger` z ikoną `aria-hidden` (`✕`).
- [ ] **Step 4: Run** `npm run test:storybook` → PASS (wszystkie, także stare).
- [ ] **Step 5: Commit** `feat(ui): add text field with Signal Forms support`

### Task 2: Slice `auth` (akcje, reducer, selektory, `sessionStorage`)

**Files:**
- Create: `frontend/src/app/store/auth/auth.actions.ts`, `auth.reducer.ts`, `auth.selectors.ts`, `auth.storage.ts`, `auth.reducer.spec.ts`, `auth.storage.spec.ts`
- Delete: `frontend/src/app/store/auth/.gitkeep`

**Interfaces:**
- Produces:
  - `AuthActions` (`createActionGroup`, source `'Auth'`): `login({ username: string; password: string })`, `loginSuccess({ token: string; expiresAt: number; username: string })`, `loginFailure({ error: string })`, `logout({ reason: 'manual' | 'expired' | 'unauthorized' })`.
  - `AuthState` jak w spec; `initialAuthState`; `authFeatureKey = 'auth'`; `authReducer`.
  - Selektory: `selectAuth`, `selectToken`, `selectExpiresAt`, `selectUsername`, `selectIsAuthenticated` (`token !== null`), `selectLoginStatus`, `selectLoginError`, `selectSessionExpired`.
  - `AUTH_STORAGE_KEY = 'coi-cf.auth'`; `authStorageMetaReducer(reducer): reducer` (zapis po każdej akcji, odczyt na `@ngrx/store/init`, odrzuca wpis z `expiresAt <= Date.now()` i nieczytelny).

- [ ] **Step 1: Write failing specs** – `auth.reducer.spec.ts`:
  - `login sets pending and clears error and sessionExpired` (status `'pending'`, `error: null`, `sessionExpired: false`, hasło nigdzie w stanie: `JSON.stringify(state)` nie zawiera hasła),
  - `loginSuccess stores token, expiresAt, username and idles`,
  - `loginFailure sets error status and message`,
  - `logout clears token; expired/unauthorized set sessionExpired, manual does not`,
  - `logout is idempotent` (logout na stanie bez tokenu zwraca ten sam obiekt stanu – `toBe`).
  `auth.storage.spec.ts` (`sessionStorage.clear()` w `beforeEach`):
  - `persists token after loginSuccess` (wpis pod `coi-cf.auth` z `token`, `expiresAt`, `username`, bez klucza `password`),
  - `removes entry on logout`,
  - `restores valid entry on init`,
  - `drops expired entry on init` (`expiresAt = Date.now() - 1`),
  - `ignores corrupted storage entry` (`'{'`, `'{"token":1}'` i `sessionStorage.getItem` rzucający – stan początkowy, bez wyjątku).
- [ ] **Step 2: Run** `npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement** akcje, reducer (`createReducer` + `on`), selektory (`createFeatureSelector`/`createSelector`), meta-reducer (try/catch wokół `sessionStorage`; status/błąd/`sessionExpired` nieutrwalane; walidacja kształtu: `token` string, `expiresAt` number, `username` string|null).
- [ ] **Step 4: Run** `npx ng test --watch=false` → PASS.
- [ ] **Step 5: Commit** `feat(auth): add auth state with session storage persistence`

### Task 3: Komunikaty błędów i interceptory

**Files:**
- Create: `frontend/src/app/core/api-error.ts`, `api-error.spec.ts`, `auth.interceptor.ts`, `error.interceptor.ts`, `interceptors.spec.ts`
- Delete: `frontend/src/app/core/.gitkeep`

**Interfaces:**
- Consumes: `selectToken`, `AuthActions.logout` (Task 2).
- Produces: `TOKEN_URL = '/api/v1/auth/token'`; `toUserMessage(error: HttpErrorResponse): string`; `authInterceptor: HttpInterceptorFn`; `errorInterceptor: HttpInterceptorFn`.

- [ ] **Step 1: Write failing specs** – `api-error.spec.ts`: po jednym teście na każdy wiersz mapy komunikatów z Global Constraints (problem+json `{ code, detail }` jako `error` w `HttpErrorResponse`), plus `falls back to detail`, `falls back to generic message with request id` (nagłówek `X-Request-ID: abc` → „Wystąpił nieoczekiwany błąd (kod zgłoszenia: abc)”). `interceptors.spec.ts` (`provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]))`, `provideHttpClientTesting()`, `provideMockStore` z tokenem `t1`):
  - `adds bearer to /api/ requests` (`/api/v1/dictionaries` → `Authorization: Bearer t1`),
  - `no bearer for token endpoint`, `no bearer for other hosts` (`https://example.com/api/x`), `no bearer without token`,
  - `401 dispatches logout unauthorized` (dla `/api/v1/dictionaries`; `store.dispatch` spy → `AuthActions.logout({ reason: 'unauthorized' })`), błąd nadal propagowany do subskrybenta,
  - `401 on token endpoint does not logout`.
- [ ] **Step 2: Run** `npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement** `toUserMessage`, `authInterceptor` (`store.selectSignal(selectToken)` przez `inject(Store)`), `errorInterceptor` (`catchError` → dispatch przy 401 → `throwError`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(auth): add API error messages and auth/error interceptors`

### Task 4: Efekty i guardy

**Files:**
- Create: `frontend/src/app/store/auth/auth.effects.ts`, `auth.effects.spec.ts`, `frontend/src/app/core/auth.guard.ts`, `auth.guard.spec.ts`

**Interfaces:**
- Consumes: `AuthActions`, selektory (Task 2), `toUserMessage` (Task 3), `AuthService.issueTokenApiV1AuthTokenPost({ body: { username, password } })` z `shared/api/services/auth.service.ts`.
- Produces: `AuthEffects` (klasa z `login$`, `loginSuccess$` (nawigacja), `expiryTimer$`, `logout$` (nawigacja)); `safeReturnUrl(raw: string | null): string`; `authGuard: CanActivateFn`; `guestGuard: CanActivateFn`.

- [ ] **Step 1: Write failing specs** – `auth.effects.spec.ts` (`provideMockActions`, `provideMockStore`, mock `AuthService`, spy `Router.navigateByUrl`, fałszywe timery Vitest `vi.useFakeTimers()`):
  - `login success maps to loginSuccess with expiresAt` (`expires_in: 60`, `Date.now()` zamrożony → `expiresAt = now + 60000`, `username` z akcji),
  - `login failure maps to loginFailure with user message` (401 `INVALID_CREDENTIALS` → „Nieprawidłowy login lub hasło”),
  - `navigates to returnUrl after login` (`?returnUrl=/import` w `router.routerState`/`ActivatedRoute` – użyj `Router.parseUrl(router.url)` z URL `/login?returnUrl=%2Fwynik%2F1` → `/wynik/1`),
  - `rejects external returnUrl` (`safeReturnUrl('//evil.com')`, `safeReturnUrl('https://evil.com')`, `safeReturnUrl(null)` → `/import`),
  - `expiry timer dispatches logout expired` (po `loginSuccess` z `expiresAt = now + 1000`; `vi.advanceTimersByTime(1000)` → `logout({ reason: 'expired' })`; nowy `loginSuccess` anuluje stary timer),
  - `restored session starts timer` (stan startowy z tokenem i `expiresAt` w przyszłości → timer startuje po `ROOT_EFFECTS_INIT`),
  - `logout navigates to /login`, `unauthorized after manual logout does nothing` (stan bez tokenu + `logout('unauthorized')` → brak nawigacji).
  `auth.guard.spec.ts`: `authGuard allows valid token`, `guard rejects expired token` (token + `expiresAt < now` → `UrlTree` `/login?returnUrl=…`), `authGuard redirects without token with returnUrl`, `guestGuard sends authenticated user to /import`, `guestGuard allows anonymous`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Idempotencję stanu zapewnia reducer (Task 2). `logout$` (bez dispatchu): `filter(() => !router.url.startsWith('/login'))` → `navigateByUrl('/login')` dla `manual`, a dla `expired`/`unauthorized` `'/login?returnUrl=' + encodeURIComponent(router.url)` – kolejne 401 trafiają już na `/login` i są ignorowane. `expiryTimer$`: `merge(loginSuccess → expiresAt, ROOT_EFFECTS_INIT → expiresAt ze stanu, jeśli token jest)` → `switchMap(at => timer(Math.max(0, at - Date.now())))` → `logout({ reason: 'expired' })`, z `takeUntil`/`switchMap` anulowanym przez `logout`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(auth): add auth effects and route guards`

### Task 5: Ekran logowania, routing, powłoka, konfiguracja

**Files:**
- Create: `frontend/src/app/features/login/login-page.ts`, `login-page.html`, `login-page.stories.ts`, `frontend/src/app/features/import/import-page.ts`, `frontend/src/app/store/auth/auth-devtools.ts` (+ `auth-devtools.spec.ts`)
- Delete: `frontend/src/app/features/login/.gitkeep`, `frontend/src/app/features/import/.gitkeep`
- Modify: `frontend/src/app/app.config.ts`, `app.routes.ts`, `app.ts`, `app.html`, `app.css`, `app.spec.ts`

**Interfaces:**
- Consumes: wszystko z Task 1–4.
- Produces: `LoginPage`, `ImportPage` (zaślepka), trasy: `''` → redirect `/import`, `/login` (`guestGuard`), `/import` (`authGuard`), `**` → `/import`; `authActionSanitizer(action)` maskujący `password` jako `'***'`.

- [ ] **Step 1: Write failing tests** – `auth-devtools.spec.ts`: `sanitizer masks password` (`login({username:'dev',password:'x'})` → `password: '***'`, inne akcje bez zmian). `app.spec.ts` (przepisany): `shows topbar with username when authenticated` (mock store, `username: 'dev'` → tekst `dev` i przycisk „Wyloguj”), `hides topbar when anonymous`, `Wyloguj dispatches logout manual`. `login-page.stories.ts` (`UI/…` nie – tytuł `Ekrany/Logowanie`; `provideMockStore`): story `Default` – pusty submit → komunikaty „Pole wymagane” pod oboma polami i fokus na „Login”, wpisanie danych + submit → dispatch `login({ username, password })`; story `Error` (stan `status: 'error', error: 'Nieprawidłowy login lub hasło'`) → `role="alert"` z tym tekstem; story `Pending` → przycisk „Logowanie…” `disabled`; story `SessionExpired` → komunikat „Sesja wygasła, zaloguj się ponownie”.
- [ ] **Step 2: Run** `npx ng test --watch=false` i `npm run test:storybook` → FAIL.
- [ ] **Step 3: Implement.** `app.config.ts`: `provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]))`, `provideStore({ [authFeatureKey]: authReducer }, { metaReducers: [authStorageMetaReducer] })`, `provideEffects(AuthEffects)`, `provideStoreDevtools({ maxAge: 25, logOnly: !isDevMode(), actionSanitizer: authActionSanitizer })`, `provideApiConfiguration('')` zostaje. `LoginPage`: Signal Forms `form(signal({ username: '', password: '' }), p => { required(p.username, { message: 'Pole wymagane' }); required(p.password, { message: 'Pole wymagane' }) })`, `app-text-field` z `[formField]` i `[error]` z błędów pola (pokazywane po próbie wysyłki), `<form (submit)>` z `preventDefault`, fokus na pierwszym błędnym polu, karta wyśrodkowana. `app.html`: `@if (isAuthenticated())` topbar (`appName="Cyfryzacja formularzy"`, `[userName]="username() ?? 'konto techniczne'"`, link „Import” z `routerLink`/`aria-current`), potem `<router-outlet />`; usuń szablon startowy i style z `app.css`.
- [ ] **Step 4: Run** oba zestawy testów → PASS; `npx ng build` → sukces.
- [ ] **Step 5: Commit** `feat(auth): add login page, routing and app shell`
