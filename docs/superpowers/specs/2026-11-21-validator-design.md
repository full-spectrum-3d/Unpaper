# Ekran „Walidator”

Data: 2026-11-21 · Gałąź: `feat/validator` · Spec techniczna: §9.1 (widok Walidator), §7.3 (reguły R01–R15)

## Po co

Jury i urzędnik mają móc sprawdzić dowolny JSON formularza względem reguł COI: wygenerowany przez system, poprawiony ręcznie albo przyniesiony z zewnątrz. Spec §9.1: „wklejenie lub wgranie JSON → `/forms/validate` → lista błędów”. Użytkownik wybrał wariant B: lista z linkami do miejsca w sformatowanym JSON-ie oraz wejście z ekranu wyniku („Sprawdź w walidatorze”).

Sukces: na ekranie `/validator` użytkownik wkleja albo wgrywa JSON i klika „Sprawdź”. Widzi „JSON spełnia reguły COI” albo liczbę błędów i ostrzeżeń z listą. „Pokaż w JSON” przewija sformatowany JSON do podświetlonego fragmentu i ustawia na nim fokus. Błąd składni widzi od razu, z linią i kolumną, bez wysyłania do backendu.

## Cele

- Trasa `/validator` (za logowaniem) i pozycja „Walidator” w górnym menu obok „Import”.
- Wklejenie JSON-a w pole tekstowe albo wgranie pliku `.json` (wczytywany do pola).
- Walidacja składni po stronie klienta, potem `POST /api/v1/forms/validate`.
- Wynik: podsumowanie, lista błędów, lista ostrzeżeń, sformatowany JSON z podświetleniem.
- Wspólny komponent widoku JSON (`app-json-view`) dla ekranu wyniku i walidatora.
- Przycisk „Sprawdź w walidatorze” na ekranie wyniku, który otwiera `/validator?item=<id>` z formularzem z kolejki.

## Poza zakresem

- Podgląd wklejonego formularza w rendererze (jest na ekranie wyniku).
- Autonaprawa (`/forms/validate` jej nie robi). Pobieranie poprawionego JSON-a.
- Edytor z kolorowaniem składni.

## Anty-cele

- Wysyłanie do backendu tekstu, który nie jest poprawnym obiektem JSON.
- Pokazywanie nieaktualnego wyniku bez ostrzeżenia, gdy użytkownik zmienił JSON po sprawdzeniu.
- Dwie kopie logiki podświetlenia, przewijania i fokusu (ekran wyniku i walidator).

## Ograniczenia

- Angular 22 jak dotąd (sygnały, `input()/output()`, `inject()`, `host: {}`, bez jawnego `ChangeDetectionStrategy`), NgRx tylko do odczytu kolejki, Tailwind 4 z tokenami, bez nowych zależności.
- Wywołanie przez wygenerowany klient (`FormsService.validateApiV1FormsValidatePost`). Odpowiedź `{ valid: boolean; errors: Issue[]; warnings: Issue[] }`, `Issue = { code; message; path? }`, typowana luźno i czytana defensywnie (jak raport).
- Błędy HTTP przez istniejące `toUserMessage` (`core/api-error.ts`).

## Podejścia (wybrane)

- **Wspólny `app-json-view`** (wybrane) zamiast kopiowania kodu z ekranu wyniku.
- **`/validator?item=<id>` + odczyt z kolejki** (wybrane) zamiast JSON-a w adresie (za duży) albo stanu routera (znika po odświeżeniu).
- **Jedna kolumna** jak ekran wyniku (prościej, działa na wąskim ekranie) zamiast dwóch kolumn.

## Projekt

### `app-json-view`: `features/result/json-view.ts`

Wyciągnięty z `result-page` bez zmiany zachowania.

```ts
// selector 'app-json-view'
lines = input.required<JsonLines>();          // z formatJson
highlight = input<string | null>(null);       // ścieżka do podświetlenia
label = input.required<string>();             // aria-label regionu
reveal(): void;                               // po renderze: przewija do pierwszej linii zakresu i fokusuje fragment
```

- Szablon i logika segmentów przeniesione 1:1: `<pre role="region" tabindex="0" [aria-label]>`, linie jako inline `span[data-line]` z własnym `\n`. Zakres to `span role="group" tabindex="-1" aria-label="Fragment JSON: <ścieżka>" class="block bg-warning-subtle focus-ring"`.
- `result-page` używa `app-json-view` z `label="Wynik konwersji w formacie JSON"`, a w `onShowInJson` woła `reveal()` przez `viewChild`. Istniejące stories ekranu wyniku muszą przechodzić bez zmian asercji.

### Ekran `features/validator/validator-page.ts` (trasa `/validator`, `title: 'Walidator'`, `authGuard`, lazy)

Układ (jedna kolumna, `max-w-[960px]`, w `<main>`):

1. `h1` „Walidator JSON” i jedno zdanie opisu: „Sprawdź, czy JSON formularza spełnia reguły COI.”
2. Pole tekstowe (`textarea`, etykieta „JSON formularza”, `font-mono`, ok. 16 linii, `spellcheck="false"`).
3. Rząd akcji: `app-file-drop` z `accept=".json"` (wczytuje tekst pliku do pola; plik większy niż 5 MB albo nie-tekstowy → komunikat „Wgraj plik .json do 5 MB.”) i przycisk główny „Sprawdź” (wyłączony przy pustym polu i w trakcie żądania; w trakcie ma tekst „Sprawdzanie…”).
4. Komunikat walidacji klienta pod polem (`text-danger`, powiązany przez `aria-describedby`, pole dostaje `aria-invalid`):
   - błąd składni: „Niepoprawny JSON: linia L, kolumna K.”, gdy pozycję da się ustalić z błędu `JSON.parse` (formaty „at position N” albo „line L column K”); w przeciwnym razie „Niepoprawny JSON.”;
   - wartość, która nie jest obiektem: „JSON musi być obiektem formularza (zaczynać się od {).”.
   Fokus wraca do pola.
5. Wynik (po udanym żądaniu), w sekcji z `h2` „Wynik” (`tabindex="-1"`, dostaje fokus po sprawdzeniu):
   - podsumowanie w `role="status"`: „JSON spełnia reguły COI.” (ikona ✓, `text-success`) albo „Znaleziono N błędów i M ostrzeżeń.” (z polską odmianą przez istniejące `pluralPl`);
   - gdy tekst zmieniono po sprawdzeniu: nad wynikiem „JSON zmieniono po sprawdzeniu. Sprawdź ponownie.” (`text-warning`), wynik dalej widoczny;
   - `h3` „Błędy (N)” i `h3` „Ostrzeżenia (M)”: listy jak w raporcie (kod `font-mono`, komunikat). Przycisk „Pokaż w JSON” (`aria-label="Pokaż w JSON: <kod>"`) pokazujemy, gdy `path` istnieje w `ranges`. W przeciwnym razie ścieżka tekstem (`text-fg-muted`). Pusta lista: „Brak”;
   - `h3` „Sformatowany JSON” i `app-json-view` z `label="Sprawdzany JSON"` dla JSON-a z chwili sprawdzenia (nie z bieżącego tekstu).
6. Błąd HTTP: komunikat z `toUserMessage` w `role="alert"` nad wynikiem. Poprzedni wynik znika.

### Wejście z ekranu wyniku

- Na ekranie wyniku, w akcjach karty obok „Pobierz .json”: link-przycisk „Sprawdź w walidatorze” → `/validator?item=<id>`.
- Walidator czyta `item` z query (`withComponentInputBinding`, `item = input<string>()`). Jeśli w kolejce jest wiersz `done` o tym `id`, wstawia do pola `JSON.stringify(result, null, 2)` i od razu uruchamia sprawdzenie. Jeśli nie ma: pole puste i informacja „Nie znaleziono wyniku do sprawdzenia. Wklej JSON ręcznie.”

### Nawigacja

- `app.html`: druga pozycja w `app-topbar`: `<a routerLink="/validator" routerLinkActive ariaCurrentWhenActive="page">Walidator</a>`.
- `app.routes.ts`: trasa przed `**`.

## Testy

- `json-view`: przeniesione asercje z ekranu wyniku (tekst identyczny ze `stringify`, jeden podświetlony zakres, `reveal()` fokusuje fragment i przewija pierwszą linię). Stories ekranu wyniku bez zmian asercji.
- Parsowanie: `parseJsonInput(text): { ok: true; value: object } | { ok: false; message: string }`, z testami dla poprawnego obiektu, tablicy, `"x"`, błędu z pozycją (linia i kolumna liczone dobrze) i błędu bez pozycji.
- Ekran (spec z `HttpTestingController` albo story z mockiem serwisu):
  - pusty tekst blokuje „Sprawdź”;
  - błąd składni nie wysyła żądania i pokazuje linię i kolumnę;
  - poprawny JSON wysyła `POST /api/v1/forms/validate` z obiektem;
  - odpowiedź `valid: true` → „JSON spełnia reguły COI.”;
  - odpowiedź z błędami → listy i przycisk „Pokaż w JSON” tylko dla istniejących ścieżek, klik podświetla i fokusuje fragment;
  - edycja po sprawdzeniu → komunikat o nieaktualnym wyniku;
  - błąd 500 → `role="alert"`;
  - `?item=<id>` z wierszem w kolejce → pole wypełnione i żądanie wysłane;
  - nieznany `id` → informacja.
- Wgranie pliku: plik `.json` trafia do pola. Plik > 5 MB daje komunikat.
- Storybook `Ekrany/Walidator`: pusty, z błędami, poprawny, błąd składni. Testy a11y przechodzą.

## Zostawione builderowi

- Dokładne klasy i odstępy (jak ekran wyniku i import).
- Czy `parseJsonInput` leży w `features/validator/`.
