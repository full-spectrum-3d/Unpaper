# Ekran importu z kolejką plików

Data: 2026-11-21 · Rozmiar: projekt (pełny design)

## Intencja
Pierwszy ekran po zalogowaniu i serce aplikacji: urzędnik wrzuca jeden lub wiele blankietów (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG), widzi postęp konwersji każdego pliku i pobiera wyniki (JSON w formacie importu Generatora Formularzy COI) pojedynczo albo wszystkie naraz jako ZIP. Spec §9.1 („Import (batch)”), §3.2 (slice `importQueue`, efekty z limitem `BATCH_CONCURRENCY`), §6.3 (reguły pliku). Wygląd: makieta A (tabela) z `docs/superpowers/specs/2026-11-21-ui-base-components-design.md`.

Backend: `/api/v1/forms/convert` jest na razie zaślepką (nie przyjmuje pliku, zwraca `dict[str, object]`). Dlatego konwersja jest za punktem wymiany (token DI) i w tym kroku zamockowana wzorcowymi JSON-ami z `wymagania/`.

## Cele
- `/import`: strefa upuszczania (`app-file-drop`), karta „Kolejka” z licznikiem i przyciskiem „Pobierz wszystkie (ZIP)”, tabela Plik / Rozmiar / Status / Akcje (makieta A).
- Walidacja klienta wg §6.3 pkt 2–5; plik niezgodny od razu w kolejce ze statusem „Błąd” i komunikatem, bez wysyłki.
- Kolejka sterowana stanem: najwyżej `BATCH_CONCURRENCY = 2` konwersje naraz; „Ponów” (błąd), „Usuń” (oczekuje / błąd / gotowe); bez „Anuluj” i bez usuwania w trakcie.
- ZIP gotowych wyników generowany w przeglądarce.
- `/result/:id`: nazwa pliku, sformatowany JSON, „Pobierz .json”, „Wróć do importu”.
- Mock konwersji za tokenem `CONVERT_FILE`, łatwy do podmiany na wygenerowany `FormsService`.
- Dostępność: `aria-live` dla zmian statusu, nazwa tabeli, powiązanie błędu wiersza z akcjami, blokada upuszczenia pliku poza strefą, kolumna „Plik” bez łamania słów w środku.

## Poza zakresem
- Pełny ekran wyniku (zakładki Podgląd formularza / JSON-drzewo / Raport), podgląd formularza (§9.3), walidator.
- Prawdziwe wywołanie `/forms/convert` z plikiem (backend jeszcze go nie przyjmuje) i parametr `mode`.
- Utrwalanie kolejki po odświeżeniu strony.
- Anulowanie trwającej konwersji.

## Anty-cele
- Obiekty `File` w store NgRx (niesserializowalne, zapychają DevTools).
- Ukryta kolejka poza store’em (bufor w operatorze RxJS) – store jest jedynym źródłem prawdy o statusach.
- Dane mocka w początkowym bundlu produkcyjnym (budżet initial 500 kB).
- Wysłanie do backendu pliku, który nie przeszedł walidacji klienta.
- Status sygnalizowany tylko kolorem; tabela bez nazwy; komunikaty błędów niepowiązane z akcjami.

## Ograniczenia
- Angular 22 (standalone, signals, `inject()`, bez jawnego `OnPush`), NgRx 22 z `@ngrx/entity`, Tailwind 4 z tokenami, istniejące `shared/ui` (`app-file-drop`, `app-card`, `table[appTable]`, `app-badge` + `FileStatus`, `app-progress`, `button[appButton]`).
- Komponenty czytają stan przez `store.selectSignal()`. Wzorzec slice’a jak w `store/auth/` (actions, reducer, selectors, effects, `createActionGroup`), rejestracja na root w `app.config.ts`.
- Komunikaty błędów konwersji przez istniejące `toUserMessage` (`core/api-error.ts`).
- Jedna nowa zależność: `fflate` (MIT) – CI odrzuca GPL/AGPL/LGPL/SSPL.
- WCAG 2.1 AA, teksty po polsku, commity bez `Co-Authored-By`.

## Podejścia
- **A. Kolejka sterowana stanem** (wybrane przez użytkownika): efekt-harmonogram po każdej zmianie kolejki startuje kolejny oczekujący plik, gdy w trakcie jest < 2; osobny efekt konwertuje jeden plik. Usuwanie i ponawianie to zwykłe zmiany stanu.
- B. `mergeMap(…, 2)` na strumieniu dodanych plików – mniej kodu, ale bufor poza store’em; usunięcie/ponowienie wymaga filtrowania i ponownego wrzucania do strumienia. Odrzucone.

## Decyzje użytkownika
- Kolejka w formie tabeli (makieta A), akcje: „Otwórz wynik” (gotowe), „Ponów” i „Usuń” (błąd), „Usuń” (oczekuje), „Usuń” (gotowe); bez „Anuluj” i „Wyczyść gotowe”; błąd walidacji jako wiersz kolejki.
- „Otwórz wynik” w tym kroku jako prosty widok JSON-a z „Pobierz .json”.
- Przepływ z playbacku zaakceptowany w całości (walidacja, limit 2, ZIP z `(2)` przy powtórzonych nazwach, mock z `blad` w nazwie → błąd, czyszczenie kolejki po odświeżeniu z ostrzeżeniem `beforeunload` przy trwającym przetwarzaniu, dostępność).
- Silnik: wariant A.

## Projekt

### Struktura plików
```
src/app/
  store/import-queue/   import-queue.actions.ts, import-queue.reducer.ts (EntityAdapter),
                        import-queue.selectors.ts, import-queue.effects.ts
  features/import/      import-page.ts (+ .html), file-validation.ts, file-registry.ts,
                        convert-file.ts (token CONVERT_FILE + typ), convert-file.mock.ts,
                        mock-forms/ (2 wzorcowe JSON-y, ładowane leniwie), zip-results.ts
  features/result/      result-page.ts (+ .html)
  app.routes.ts         + /result/:id (authGuard)
  app.config.ts         + slice importQueue, ImportQueueEffects, provider CONVERT_FILE (mock)
```

### Model
- `QueueItem = { id: string; name: string; size: number; status: FileStatus; error: string | null; retryable: boolean; result: unknown | null; startedAt: number | null; durationMs: number | null }` – `retryable` jest `false` dla błędów walidacji klienta (ustawiane w `filesAdded`) i `true` dla błędów konwersji (`convertFailed`) (`FileStatus` z `shared/ui/badge`: `'pending' | 'processing' | 'done' | 'error'`). `id` z `crypto.randomUUID()`.
- Stan: `EntityState<QueueItem>` (adapter z `sortComparer: false` – kolejność dodania).
- Akcje (`createActionGroup`, source `'Import Queue'`): `filesAdded({ items: QueueItem[] })` (już po walidacji: niezgodne mają `status: 'error'` i komunikat), `convertStarted({ id, startedAt })`, `convertSucceeded({ id, result, durationMs })`, `convertFailed({ id, error })`, `retry({ id })` (→ `pending`, czyści błąd), `removed({ id })`.
- Reguły w reducerze (czysty, nie czyta rejestru plików): `retry` tylko gdy `status === 'error' && retryable`; `removed` ignorowane dla `processing`. Przycisk „Ponów” widoczny tylko przy `retryable`. Brak pliku w rejestrze przy starcie konwersji obsługuje defensywnie `convert$` (patrz Efekty).
- Selektory: `selectQueueItems`, `selectQueueItem(id)`, `selectQueueCounts` (`{ total, done, error, processing, pending }`), `selectDoneItems`, `selectNextPending` (pierwszy `pending` w kolejności), `selectProcessingCount`.

### Walidacja klienta (`file-validation.ts`)
`validateFile(file: File): string | null` – kolejność i komunikaty:
1. nazwa > 250 znaków → „Nazwa pliku jest za długa (maks. 250 znaków).”
2. nazwa zawiera którykolwiek z `; : > < / \ | ' * % $` → „Nazwa pliku zawiera niedozwolone znaki: ; : > < / \ | ' * % $”
3. rozmiar > 20 MB (`MAX_FILE_SIZE_MB = 20`, stała zgodna z domyślnym backendem) → „Plik jest za duży (maks. 20 MB).”
4. rozszerzenie (bez rozróżniania wielkości liter) spoza `pdf, doc, docx, ods, xlsx, jpg, jpeg, png` → „Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.”
Plik bez rozszerzenia → reguła 4. Pusty plik (0 B) przechodzi (decyduje backend).
- Błąd walidacji klienta **nie jest ponawialny** (ponowienie dałoby ten sam wynik): wiersz ma tylko „Usuń”. „Ponów” tylko dla błędów konwersji.

### Rejestr plików (`file-registry.ts`)
Serwis root: `add(id, file)`, `get(id): File | undefined`, `delete(id)`. Plik usuwany z rejestru przy `removed`. Gotowe pliki zostają w rejestrze (potrzebne tylko przy ponowieniu – można je zwolnić po sukcesie; decyzja: zwalniamy po `convertSucceeded`, bo gotowego nie da się ponowić).

### Efekty (`import-queue.effects.ts`)
- `schedule$`: nasłuch na `filesAdded`, `convertSucceeded`, `convertFailed`, `retry`, `removed` → `concatLatestFrom` (`selectProcessingCount`, `selectQueueItems`) → dopóki `processing < BATCH_CONCURRENCY` startuje kolejne `pending` w kolejności (`convertStarted` dla każdego; może wysłać 0–2 akcje naraz).
- `convert$`: `convertStarted` → `mergeMap` (bez limitu – limit pilnuje `schedule$`) → `inject(CONVERT_FILE)(file)` → `convertSucceeded` / `convertFailed` (`toUserMessage` dla `HttpErrorResponse`, inaczej „Wystąpił nieoczekiwany błąd”). Brak pliku w rejestrze → `convertFailed` z „Plik niedostępny – dodaj go ponownie”.
- `announce`: brak efektu – komunikaty `aria-live` liczy komponent z różnicy statusów.

### Konwersja (`convert-file.ts`, `convert-file.mock.ts`)
- `CONVERT_FILE = new InjectionToken<(file: File) => Observable<unknown>>('CONVERT_FILE')`.
- Mock: opóźnienie 1500–4000 ms (losowe), plik z `blad` w nazwie (bez rozróżniania wielkości liter) → błąd `HttpErrorResponse` 503 z problem+json `{ code: 'LLM_UNAVAILABLE' }`; inaczej na zmianę jeden z dwóch wzorcowych JSON-ów, ładowanych `import()` z `mock-forms/` (osobny chunk, poza initial bundle). `toUserMessage` musi mieć komunikat dla `LLM_UNAVAILABLE`: „Usługa analizy formularzy jest chwilowo niedostępna. Spróbuj ponownie.” (dopisać do mapy w `core/api-error.ts`) oraz `PROCESSING_TIMEOUT`: „Przetwarzanie trwało zbyt długo. Spróbuj ponownie.”
- Podmiana na backend (poza zakresem): provider zwracający funkcję wołającą `FormsService.convertApiV1FormsConvertPost` – zmiana jednego providera w `app.config.ts`.

### ZIP (`zip-results.ts`)
`buildResultsZip(items: { name: string; result: unknown }[]): Blob` przez `fflate` (`zipSync`, `strToU8`). Nazwa wpisu: nazwa pliku bez ostatniego rozszerzenia + `.json`; powtórzenia → `nazwa (2).json`, `nazwa (3).json`. JSON sformatowany (`JSON.stringify(result, null, 2)`). Plik do pobrania: `wyniki-konwersji.zip` (przez `URL.createObjectURL` + tymczasowy `<a download>`, URL zwalniany po kliknięciu). Przycisk wyłączony, gdy `done === 0`.

### Ekran importu (`import-page`)
- Nagłówek „Import formularzy” (`h1`), `app-file-drop` (`maxSizeMb` = 20), karta „Kolejka” (`h2` z id – nazwa tabeli przez `aria-labelledby`), licznik „N plików · X gotowych · Y błędów” (polskie formy liczebników: 1 plik / 2–4 pliki / 5+ plików; tak samo „gotowy/gotowe/gotowych”, „błąd/błędy/błędów”), „Pobierz wszystkie (ZIP)”.
- Pusta kolejka: zamiast tabeli tekst „Kolejka jest pusta. Dodaj pliki powyżej.”
- Tabela: kolumny Plik (szeroka: pozostałe kolumny `w-px whitespace-nowrap`, nazwa z `[overflow-wrap:anywhere]`), Rozmiar (KB/MB po polsku, przecinek dziesiętny), Status (`app-badge`; przy `processing` także `app-progress` z etykietą „Przetwarzanie <nazwa>”; przy `done` czas „12 s”), Akcje.
- Komunikat błędu pod nazwą pliku z id; przyciski w wierszu `aria-label` z nazwą pliku („Ponów formularz.jpe”, „Usuń formularz.jpe”, „Otwórz wynik Deklaracja….docx”) i `aria-describedby` → id komunikatu błędu (dla wierszy z błędem).
- Region `aria-live="polite"` (wizualnie ukryty) z ostatnim komunikatem: „<nazwa>: gotowe” / „<nazwa>: błąd – <komunikat>”.
- `window` `dragover`/`drop` z `preventDefault` poza strefą upuszczania (plik upuszczony obok nie otwiera się w przeglądarce) – rejestrowane na czas życia strony importu.
- `beforeunload` z ostrzeżeniem, gdy `processing + pending > 0`.

### Ekran wyniku (`result-page`, `/result/:id`, `authGuard`)
- Przycisk-link „← Wróć do importu”, nagłówek z nazwą pliku, „Pobierz .json” (nazwa jak w ZIP, bez sufiksu), `<pre>` z `JSON.stringify(result, null, 2)` w `font-mono`, przewijany (`overflow-auto`, `tabindex="0"` dla przewijania klawiaturą, `aria-label="Wynik konwersji w formacie JSON"`).
- Nieznane `id` albo status inny niż `done` → komunikat „Wynik niedostępny. Wróć do importu i przetwórz plik ponownie.” z linkiem.
- Tytuł trasy: „Wynik”.

## Testy
- Unit: `validateFile` (każda reguła, granice 250 znaków i 20 MB, wielkość liter rozszerzenia, brak rozszerzenia), reducer (wszystkie akcje, `retry` tylko dla błędu konwersji, `removed` ignorowane w trakcie), selektory (liczniki, kolejność `selectNextPending`), efekty (`schedule$` nie przekracza 2; po sukcesie startuje następny; usunięty oczekujący nie startuje; ponowiony startuje; brak pliku w rejestrze → błąd), `buildResultsZip` (nazwy, powtórzenia, zawartość po `unzipSync`), polskie liczebniki, mock (opóźnienie z fałszywymi timerami, `blad` → 503 `LLM_UNAVAILABLE`), nowe komunikaty w `toUserMessage`.
- Storybook: ekran importu z zamockowanym store’em w stanach: pusta kolejka, mieszana kolejka (4 statusy), a11y w motywie `tool`; ekran wyniku (gotowy, niedostępny).
- Integracja: test z prawdziwym store i mockiem `CONVERT_FILE` (fałszywe timery): dodanie 3 plików → najwyżej 2 `processing` naraz → wszystkie `done`.

## Rozstrzygnięcia po przeglądzie wykonawcy (decyzje autora designu)
1. **Ponawialność:** pole `retryable` w `QueueItem` (wyżej) zamiast wnioskowania ze `startedAt` – jawne w modelu, w szablonie i w testach.
2. **Commity:** bez linii `Co-Authored-By` ani innego podpisu AI (wymóg użytkownika, nadrzędny wobec przypomnień środowiska).
3. **Dane mocka:** dwa wzorcowe JSON-y kopiowane z `wymagania/` do `features/import/mock-forms/` (nie importowane spoza katalogu aplikacji) i ładowane `import()`.
4. **`concatLatestFrom`:** jeśli w NgRx 22 nie ma go w `@ngrx/operators`/`@ngrx/effects`, użyć `withLatestFrom` ze stanem.

## Zostawione wykonawcy
- Dokładny układ pól i klas Tailwind w granicach makiety A.
- Czy liczniki polskie są osobnym pipe’em, czy funkcją.
- Sposób wywołania pobierania pliku (helper w `features/import`).
- Wybór między `effect()` a efektem NgRx dla ogłoszeń `aria-live` (preferowany `computed` + porównanie poprzedniego stanu w komponencie).
