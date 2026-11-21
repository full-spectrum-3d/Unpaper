# Logowanie we froncie (auth)

Data: 2026-11-21 · Rozmiar: projekt (pełny design)

## Intencja
Pierwszy działający przepływ aplikacji: urzędnik (w tej wersji jury i zespół) loguje się kontem technicznym, a wszystkie kolejne ekrany (import, wynik, walidator) są dostępne tylko z ważnym tokenem. Logowanie ustawia też konwencje, z których skorzysta reszta frontu: pierwszy slice NgRx, interceptory HTTP, routing z guardem, powłoka aplikacji z topbarem i pierwsze pole formularza.

Kontekst: backend ma gotowe `POST /api/v1/auth/token` (formularz OAuth2: `username`, `password`) zwracające `TokenResponse {access_token, token_type: "bearer", expires_in}` (domyślnie 3600 s, bez odświeżania) oraz wspólny format błędów `application/problem+json` (RFC 9457) z polem `code` (`INVALID_CREDENTIALS`, `INVALID_TOKEN`, `NOT_AUTHENTICATED`, `FORBIDDEN`, …) i nagłówkiem `X-Request-ID`. Klient tego endpointu jest już wygenerowany: `AuthService.issueTokenApiV1AuthTokenPost()` w `frontend/src/app/shared/api/`.

## Cele
- Ekran `/login` z formularzem login/hasło, komunikatami błędów po polsku i stanem „trwa logowanie”.
- Slice `auth` w NgRx: token i moment wygaśnięcia, kopia w `sessionStorage` przywracana przy starcie aplikacji.
- Automatyczne wylogowanie: po upływie `expires_in`, po odpowiedzi 401 z API i ręcznie przyciskiem „Wyloguj” w topbarze.
- `auth.interceptor` (nagłówek `Authorization: Bearer …` tylko dla żądań do `/api/`) i `error.interceptor` (zamiana błędu HTTP na komunikat po polsku).
- Routing: `/login` publiczny; reszta pod guardem; po zalogowaniu powrót do `returnUrl` albo do `/import`.
- Powłoka aplikacji (layout) z `app-topbar` dla zalogowanego użytkownika; zastąpienie szablonu startowego w `app.html`.
- Komponent `app-text-field` (etykieta, opis, komunikat błędu, `type` text/password) w `shared/ui`, ze story w Storybooku.

## Poza zakresem
- OIDC / broker tożsamości (Węzeł Krajowy) – przyszła ścieżka z `docs/architecture/wezel-krajowy.md`; projektujemy tylko tak, żeby jej nie blokować.
- Wiele kont, role w UI, „Zapamiętaj mnie”, ostrzeżenie przed wygaśnięciem sesji, odświeżanie tokenu.
- Prawdziwe ekrany importu/wyniku/walidatora – `/import` dostaje tymczasową stronę-zaślepkę.
- Proxy / środowisko dev (gałąź `feat/local-dev-env` świadomie nie scalona).

## Anty-cele
- Token w `localStorage`, w cookies ustawianych przez front albo w URL.
- Token wysyłany do innych hostów niż własne `/api/`.
- Hasło przechowywane gdziekolwiek poza polem formularza (nie w store, nie w logach, nie w DevTools).
- Komunikat „nieprawidłowe hasło”, gdy faktyczny problem to brak połączenia lub wyłączone logowanie.
- Status/błąd sygnalizowany tylko kolorem; formularz niedostępny z klawiatury.

## Ograniczenia
- Angular 22 (standalone, signals, `input()`/`output()`, bez jawnego `OnPush` – domyślny), Tailwind 4 z tokenami semantycznymi (`frontend/src/styles/tokens.css`), istniejące komponenty `shared/ui` (`button[appButton]`, `app-card`, `app-topbar`).
- NgRx 22 już skonfigurowany w `app.config.ts` (`provideStore()`, `provideEffects()`, `provideStoreDevtools()`).
- Wywołania HTTP tylko przez wygenerowany klient (`AuthService`), bez ręcznego `HttpClient` do `/auth/token` – inaczej `api:check` nie wykryje rozjazdu kontraktu.
- WCAG 2.1 AA: etykiety `for`/`id`, `aria-describedby` dla opisu i błędu, `aria-invalid`, fokus na pierwszym polu z błędem / na komunikacie błędu logowania, kontrast z tokenów.
- Teksty UI po polsku. Commity bez linii `Co-Authored-By`.

## Podejścia
- **1. NgRx: slice `auth` + efekty + meta-reducer do `sessionStorage`** (wybrane przez użytkownika). Zgodne ze spec §9.1/§9.2 i z gotową konfiguracją NgRx; ustawia wzorzec dla `import-queue`.
- 2. Serwis na sygnałach – mniej kodu, ale łamie decyzję ze spec i daje dwa wzorce stanu. Odrzucone.
- 3. `@ngrx/signals` (SignalStore) – nowa zależność obok `@ngrx/store`. Odrzucone.

## Decyzje użytkownika
- Logują się tylko jury i zespół, jedno konto techniczne → prosto, bez OIDC; slice `auth` niezależny od źródła tokenu.
- Zachowanie z playbacku zaakceptowane: guard + `returnUrl` (domyślnie `/import`), token + `expiresAt` w store z kopią w `sessionStorage` (bez `localStorage`), trzy drogi wylogowania (przycisk, timer, 401) z komunikatem „Sesja wygasła, zaloguj się ponownie” (bez komunikatu przy ręcznym wylogowaniu), `auth.interceptor` tylko dla `/api/`, `error.interceptor` z komunikatami po polsku według `code`, osobny komunikat, gdy `/auth/token` zwraca 404 („Logowanie hasłem jest wyłączone w tej konfiguracji”), bez „Zapamiętaj mnie” i bez ostrzeżenia przed wygaśnięciem.
- Stan: wariant 1 (NgRx).

## Projekt

### Struktura plików
```
src/app/
  store/auth/        auth.actions.ts, auth.reducer.ts, auth.effects.ts,
                     auth.selectors.ts, auth.storage.ts (meta-reducer)
  core/              auth.interceptor.ts, error.interceptor.ts,
                     auth.guard.ts, api-error.ts (mapowanie problem+json → komunikat)
  features/login/    login-page.ts (+ .html)
  features/import/   import-page.ts (tymczasowa zaślepka „Import – wkrótce”)
  shared/ui/text-field/  text-field.ts, text-field.stories.ts
  app.ts / app.html  powłoka: topbar (gdy zalogowany) + <router-outlet>
  app.routes.ts      /login, '' → /import, /import (guard), ** → /import
```

### Stan `auth`
- `AuthState = { token: string | null; expiresAt: number | null; username: string | null; status: 'idle' | 'pending' | 'error'; error: string | null; sessionExpired: boolean }`. `expiresAt` w ms epoki, liczone w efekcie jako `Date.now() + expires_in * 1000`.
- Akcje: `login({ username, password })`, `loginSuccess({ token, expiresAt })`, `loginFailure({ error })`, `logout({ reason: 'manual' | 'expired' | 'unauthorized' })`.
- Hasło jest tylko w payloadzie `login` (potrzebne efektowi), nie trafia do stanu; reducer go nie zapisuje. Ryzyko: DevTools pokazuje payload akcji – akceptowalne dla konta demo; `provideStoreDevtools` z `actionSanitizer` maskującym `password` (zostawione wykonawcy jako jedna linia, ale wymagane).
- Selektory: `selectToken`, `selectIsAuthenticated` (token i `expiresAt > now` – sprawdzane przy odczycie, bo czas płynie), `selectLoginStatus`, `selectLoginError`, `selectSessionExpired`.
- Meta-reducer `auth.storage.ts`: po każdej akcji zapisuje `{token, expiresAt}` do `sessionStorage` pod kluczem `coi-cf.auth` (lub usuwa przy `token === null`); przy inicjalizacji (`@ngrx/store/init`) wczytuje i odrzuca wpis wygasły lub nieczytelny (try/catch – `sessionStorage` może rzucić). Status/błąd nie są utrwalane.

### Efekty
- `login$`: `AuthService.issueTokenApiV1AuthTokenPost({ body: { username, password } })` → `loginSuccess` / `loginFailure` z komunikatem z `api-error.ts`.
- `loginSuccess$`: nawigacja do `returnUrl` z query (tylko ścieżki względne zaczynające się od `/`, nigdy `//` ani pełny URL – ochrona przed open redirect), domyślnie `/import`.
- `expiryTimer$`: po `loginSuccess` i po starcie z przywróconą sesją ustawia timer do `expiresAt`; po upływie `logout({ reason: 'expired' })`. Nowe logowanie/wylogowanie anuluje poprzedni timer (`switchMap`).
- `logout$`: nawigacja do `/login`; dla `expired`/`unauthorized` ustawia `sessionExpired = true` (komunikat na ekranie logowania), dla `manual` nie.

### Interceptory i guard (funkcyjne, `provideHttpClient(withInterceptors([...]))`)
- `auth.interceptor`: jeśli URL żądania zaczyna się od `/api/` (względny – root URL klienta to `''`) i jest token, dodaje `Authorization: Bearer <token>`. Nie dla `/api/v1/auth/token`.
- `error.interceptor`: przepuszcza błąd dalej (nie połyka), ale dla 401 z żądań innych niż `/auth/token` wysyła `logout({ reason: 'unauthorized' })`.
- `api-error.ts`: `toUserMessage(error: HttpErrorResponse): string` – `status 0` → „Brak połączenia z serwerem”; `problem+json` z `code` → komunikat z mapy (min.: `INVALID_CREDENTIALS` → „Nieprawidłowy login lub hasło”, `NOT_AUTHENTICATED`/`INVALID_TOKEN` → „Sesja wygasła, zaloguj się ponownie”, `FORBIDDEN` → „Brak uprawnień”, `VALIDATION_ERROR` → „Uzupełnij login i hasło”); 404 na `/auth/token` → „Logowanie hasłem jest wyłączone w tej konfiguracji”; inaczej `detail` z problem+json albo „Wystąpił nieoczekiwany błąd” + `X-Request-ID`, jeśli jest (do zgłoszenia).
- `auth.guard` (`CanActivateFn`): `selectIsAuthenticated` → `true`, inaczej `UrlTree` do `/login?returnUrl=<aktualny url>`. Na `/login` odwrotnie: zalogowany trafia na `/import`.

### Ekran logowania
- Karta na środku (`app-card`), nazwa aplikacji „Cyfryzacja formularzy”, pola „Login” i „Hasło” (`app-text-field`, `autocomplete="username"` / `"current-password"`), przycisk „Zaloguj” (`button[appButton] variant="primary" type="submit"`, wyłączony i z tekstem „Logowanie…” podczas `pending`).
- Walidacja klienta: oba pola wymagane (komunikat pod polem, `aria-invalid`), wysyłka blokowana, fokus na pierwszym błędnym polu.
- Błąd logowania jako komunikat nad przyciskiem w regionie `role="alert"`; `sessionExpired` jako komunikat informacyjny na górze.
- Formularz: Signal Forms z Angulara 22 (konwencja projektu); jeśli API okaże się niestabilne w zainstalowanej wersji – Reactive Forms (zostawione wykonawcy po sprawdzeniu w dokumentacji).

### `app-text-field`
- `label` (wymagany), `type: 'text' | 'password'` (domyślnie text), `description?`, `error?` (string – gdy ustawiony: `aria-invalid="true"` i komunikat w `text-danger` z ikoną), `autocomplete?`, wartość dwukierunkowo (`model()`), unikalne `id` per instancja, `aria-describedby` łączy opis i błąd.
- Style z tokenów (`py-field-y`, `px-field-x`, `rounded-field`, `border-border-input`, `focus-ring`), działa w motywach `tool` i `preview` (przyda się w podglądzie formularzy, §9.3).
- Story z play testami w obu motywach (jak inne komponenty `shared/ui`).

### Powłoka aplikacji
- `app.html`: `app-topbar` (nazwa „Cyfryzacja formularzy”, `userName` = login z tokenu `sub` albo stałe „konto techniczne”, link „Import” z `aria-current`, `(logout)` → `logout({ reason: 'manual' })`) widoczny tylko dla zalogowanego; pod spodem `<router-outlet>`. Szablon startowy Angulara usunięty.

## Testy
- Unit (Vitest przez `ng test`): reducer i selektory (w tym `selectIsAuthenticated` z przeszłym `expiresAt`), meta-reducer (zapis, odczyt, odrzucenie wygasłego i uszkodzonego wpisu, brak hasła w `sessionStorage`), efekty (sukces, błąd, nawigacja z bezpiecznym `returnUrl`, timer z fałszywym czasem), interceptory (`HttpTestingController`: nagłówek tylko dla `/api/`, brak dla `/auth/token` i obcych hostów, 401 → `logout('unauthorized')`), `toUserMessage`, guard.
- Storybook: `app-text-field` (stany: pusty, z opisem, z błędem, password; a11y w obu motywach); ekran logowania z zamockowanym store/HTTP (błąd, pending).
- Ręczny test dymny na prawdziwym backendzie zostawiony wykonawcy (np. lokalny `ng serve` z proxy uruchomionym doraźnie), bo gałąź z proxy nie jest scalona.

## Rozstrzygnięcia po przeglądzie wykonawcy (decyzje autora designu)
1. **Rejestracja:** slice `auth`, jego efekty i meta-reducer rejestrowane na poziomie root w `app.config.ts` (`provideStore({ auth: authReducer }, { metaReducers: [authStorage] })`, `provideEffects(AuthEffects)`), bo przywracanie sesji przy `@ngrx/store/init` i timer dla przywróconej sesji muszą działać od startu. Katalogi `store/import-queue` i `store/catalog` zostają nietknięte.
2. **Nazwa w topbarze:** `username` z formularza logowania zapisywany w stanie (`loginSuccess({ token, expiresAt, username })`) i utrwalany razem z tokenem w `sessionStorage`. Bez dekodowania JWT (backend wydaje JWT z `sub` = login, ale front nie musi go czytać – i tak nie weryfikuje podpisu). Fallback, gdy brak: „konto techniczne”.
3. **Wylogowanie idempotentne:** `logout` przy `token === null` nie zmienia stanu i nie nawiguje ponownie; równoległe 401 dają jedną nawigację, a 401 po ręcznym wylogowaniu nie pokazuje komunikatu „Sesja wygasła”.
4. **`sessionExpired`:** ustawiane przy `logout` `expired`/`unauthorized`, czyszczone przy `login` (nowa próba) i przy `loginSuccess`. Nie utrwalane – po przeładowaniu strony komunikat znika (akceptowalne).
5. **Guardy:** dwie funkcje w `auth.guard.ts`: `authGuard` (chronione trasy → `/login?returnUrl=…`) i `guestGuard` (na `/login` → zalogowany trafia na `/import`). `returnUrl` pomijany przy ręcznym wylogowaniu i gdy bieżący URL to `/login`.
6. **Wygaśnięcie a selektory:** UI (topbar, powłoka) reaguje na akcję `logout('expired')` z timera, więc selektory zostają czyste i memoizowane (`selectIsAuthenticated` = `token !== null`). Guard dodatkowo sprawdza `expiresAt > Date.now()` bezpośrednio (poza selektorem), na wypadek uśpionej karty, w której timer nie zdążył.
7. **Kontrakt `app-text-field`:** wartość jako `value = model('')` – to jednocześnie kontrakt kontrolki niestandardowej Signal Forms (`FormValueControl`), więc pole działa i z `[field]` z Signal Forms, i ze zwykłym `[(value)]`. Bez `ControlValueAccessor`. Jeśli Signal Forms w zainstalowanej wersji okaże się niedostępne, ekran logowania używa `[(value)]` z sygnałami komponentu – kontrakt pola się nie zmienia.
8. **Motywy:** oba motywy testowane w story `app-text-field`; ekran logowania tylko w motywie `tool`.
9. **`app.spec.ts`:** przepisany pod nową powłokę (test szablonu startowego usunięty).
10. **Weryfikacja:** w tej gałęzi wystarczą testy jednostkowe (`HttpTestingController`) i Storybook; test na prawdziwym backendzie poza zakresem (gałąź z proxy nie jest scalona).

## Zostawione wykonawcy
- Dokładne API Signal Forms w zainstalowanej wersji Angulara (sprawdzić w dokumentacji przed użyciem).
- Konfiguracja `actionSanitizer` w DevTools maskująca `password`.
- Wygląd zaślepki `/import`.
- Wybór między `fakeAsync`/fałszywymi timerami Vitest w teście timera.
