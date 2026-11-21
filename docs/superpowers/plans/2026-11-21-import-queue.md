# Ekran importu z kolejką Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ekran `/import` z kolejką plików (walidacja §6.3, limit 2 konwersji naraz, ponów/usuń, ZIP wyników) oraz prosty ekran `/result/:id`, na zamockowanej konwersji.

**Architecture:** Slice NgRx `importQueue` (EntityAdapter) jest jedynym źródłem prawdy o statusach; efekt-harmonogram startuje kolejne oczekujące pliki, gdy w trakcie < 2, a efekt konwersji wywołuje funkcję z tokenu `CONVERT_FILE` (mock ładujący leniwie wzorcowe JSON-y). Obiekty `File` trzyma serwis `FileRegistry`, nie store. ZIP przez `fflate`.

**Tech Stack:** Angular 22 (standalone, signals, zoneless), NgRx 22 (`@ngrx/store`, `@ngrx/effects`, `@ngrx/entity`), RxJS (`withLatestFrom` – `concatLatestFrom` nie jest dostępny bez `@ngrx/operators`), `fflate@^0.8.3` (MIT), Vitest (`ng test`), Storybook 10.

**Spec:** `docs/superpowers/specs/2026-11-21-import-queue-design.md` (sekcja „Rozstrzygnięcia” wiąże).

## Global Constraints

- `BATCH_CONCURRENCY = 2`; `MAX_FILE_SIZE_MB = 20`; rozszerzenia `pdf, doc, docx, ods, xlsx, jpg, jpeg, png` (bez rozróżniania wielkości liter).
- Komunikaty walidacji (dokładnie): „Nazwa pliku jest za długa (maks. 250 znaków).”; „Nazwa pliku zawiera niedozwolone znaki: ; : > < / \ | ' * % $”; „Plik jest za duży (maks. 20 MB).”; „Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.”
- Nowe komunikaty `toUserMessage`: `LLM_UNAVAILABLE` → „Usługa analizy formularzy jest chwilowo niedostępna. Spróbuj ponownie.”; `PROCESSING_TIMEOUT` → „Przetwarzanie trwało zbyt długo. Spróbuj ponownie.”
- Inne teksty: „Import formularzy”, „Kolejka”, „Pobierz wszystkie (ZIP)”, „Kolejka jest pusta. Dodaj pliki powyżej.”, „Plik niedostępny – dodaj go ponownie”, „Wynik niedostępny. Wróć do importu i przetwórz plik ponownie.”, „← Wróć do importu”, „Pobierz .json”; plik ZIP `wyniki-konwersji.zip`.
- `File` nigdy w store ani w akcjach. Dane mocka tylko w leniwym chunku (initial bundle bez nich; budżet 500 kB).
- Angular: standalone, `inject()`, signals/`selectSignal`, bez jawnego `OnPush`, tylko klasy semantyczne Tailwind, `focus-ring`, teksty po polsku, WCAG 2.1 AA.
- Node: `cd frontend && source ~/.nvm/nvm.sh && nvm use` (ng wymaga Node ≥ 24.15). Testy: `npx ng test --watch=false`, `npm run test:storybook`, `npx ng build` – zielone na końcu każdego zadania.
- Commity w Conventional Commits, bez linii `Co-Authored-By`.

## Review Focus

1. **Plik bez rozszerzenia lub z kropką na końcu** (`raport`, `raport.`) – błąd rozszerzenia, nie wyjątek → test `rejects missing extension` w Task 1.
2. **Usunięcie oczekującego pliku, zanim harmonogram go podejmie** – nie startuje i nie zajmuje slotu → test `removed pending is never started` w Task 3.
3. **Dodanie 10 plików naraz** – nigdy więcej niż 2 `processing` w żadnej chwili → test integracyjny `never more than two processing` w Task 3.
4. **Dwa pliki o tej samej nazwie w ZIP** – `nazwa.json` i `nazwa (2).json`, nic nie nadpisane → test `dedupes names` w Task 4.
5. **Odświeżenie strony wyniku / nieznane id** – komunikat „Wynik niedostępny…”, nie biała strona → story `Unavailable` w Task 6.

---

### Task 1: Walidacja plików, formatowanie i nowe komunikaty błędów

**Files:**
- Create: `frontend/src/app/features/import/file-validation.ts`, `file-validation.spec.ts`, `frontend/src/app/features/import/format.ts`, `format.spec.ts`
- Modify: `frontend/src/app/core/api-error.ts`, `api-error.spec.ts`
- Delete: `frontend/src/app/features/import/.gitkeep` (jeśli jest)

**Interfaces:**
- Produces: `MAX_FILE_SIZE_MB = 20`, `ACCEPTED_EXTENSIONS: readonly string[]`, `validateFile(file: Pick<File, 'name' | 'size'>): string | null`; `formatSize(bytes: number): string` (np. `84 KB`, `1,2 MB`, `0 B`); `pluralPl(n: number, one: string, few: string, many: string): string` (wybór formy: 1 → one; 2–4 poza 12–14 → few; reszta → many); `queueSummary(c: { total: number; done: number; error: number }): string` → „4 pliki · 1 gotowy · 1 błąd”.

- [ ] **Step 1: Write failing specs** – `file-validation.spec.ts`: `accepts valid pdf` (null), `accepts uppercase extension` (`A.PDF`), `rejects name over 250` (251 znaków → komunikat 1; 250 → null), każdy zakazany znak z listy osobno (`it.each([';',':','>','<','/','\\','|',"'",'*','%','$'])`) → komunikat 2, `rejects over 20 MB` (`20*1024*1024 + 1` → komunikat 3; równo 20 MB → null), `rejects unsupported extension` (`a.jpe`), `rejects missing extension` (`raport`, `raport.` → komunikat 4), `accepts empty file` (size 0). `format.spec.ts`: `formatSize(0) === '0 B'`, `formatSize(86016) === '84 KB'`, `formatSize(1258291) === '1,2 MB'`; `pluralPl` dla 1, 2, 5, 12, 22, 25 z formami „plik/pliki/plików”; `queueSummary({total:4,done:1,error:1}) === '4 pliki · 1 gotowy · 1 błąd'`, `queueSummary({total:5,done:2,error:5}) === '5 plików · 2 gotowe · 5 błędów'`. `api-error.spec.ts`: dwa nowe kody → komunikaty z Global Constraints.
- [ ] **Step 2: Run** `npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement.** Kolejność reguł jak w spec; rozszerzenie = tekst po ostatniej kropce, gdy kropka nie jest ostatnim znakiem. `formatSize`: < 1024 → `n B`; < 1 MiB → zaokrąglone KB; inaczej MB z jednym miejscem po przecinku (`toLocaleString('pl-PL', …)` albo zamiana `.`→`,`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(import): add client file validation and Polish formatting`

### Task 2: Slice `importQueue` i rejestr plików

**Files:**
- Create: `frontend/src/app/store/import-queue/import-queue.actions.ts`, `import-queue.reducer.ts`, `import-queue.selectors.ts`, `import-queue.reducer.spec.ts`, `frontend/src/app/features/import/file-registry.ts`, `file-registry.spec.ts`
- Delete: `frontend/src/app/store/import-queue/.gitkeep`

**Interfaces:**
- Consumes: `FileStatus` z `shared/ui/badge/badge.ts`.
- Produces: `QueueItem` (pola jak w spec, z `retryable`); `ImportQueueActions` (source `'Import Queue'`): `filesAdded({ items: QueueItem[] })`, `convertStarted({ id: string; startedAt: number })`, `convertSucceeded({ id: string; result: unknown; durationMs: number })`, `convertFailed({ id: string; error: string })`, `retry({ id: string })`, `removed({ id: string })`; `importQueueFeatureKey = 'importQueue'`; `importQueueReducer`; selektory `selectQueueItems`, `selectQueueItem(id: string)` (fabryka), `selectQueueCounts` (`{ total, done, error, processing, pending }`), `selectDoneItems`, `selectProcessingCount`; `FileRegistry` (`@Injectable({ providedIn: 'root' })` albo `@Service` zgodnie z konwencją v22): `add(id, file)`, `get(id)`, `delete(id)`.

- [ ] **Step 1: Write failing specs** – `import-queue.reducer.spec.ts`: `filesAdded keeps insertion order`, `convertStarted sets processing and startedAt`, `convertSucceeded sets done, result, durationMs, clears error`, `convertFailed sets error, message, retryable true`, `retry only for retryable error` (z `retryable:false` → ten sam obiekt stanu `toBe`; z `true` → `pending`, `error: null`), `removed deletes pending, error and done`, `removed ignored while processing` (`toBe`), selektory: `counts` dla mieszanej kolejki, `selectDoneItems` tylko `done`. `file-registry.spec.ts`: add/get/delete.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`createEntityAdapter<QueueItem>({ sortComparer: false })`, `createFeatureSelector`, selektory z `adapter.getSelectors`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(import): add import queue state and file registry`

### Task 3: Konwersja (token + mock) i efekty kolejki

**Files:**
- Create: `frontend/src/app/features/import/convert-file.ts`, `convert-file.mock.ts`, `convert-file.mock.spec.ts`, `frontend/src/app/features/import/mock-forms/nadplata-podatku.json`, `mock-forms/numer-porzadkowy.json` (kopie `wymagania/konfiguracja_form_wniosekOStwierdzenieNadplatyPodatku.json` i `wymagania/konfiguracja_form_wniosekOUstalenieNumeruPorzadkowegoNieruchomosci.json`), `frontend/src/app/store/import-queue/import-queue.effects.ts`, `import-queue.effects.spec.ts`, `import-queue.integration.spec.ts`
- Modify: `frontend/tsconfig.json` (tylko jeśli `resolveJsonModule` jest wyłączone)

**Interfaces:**
- Consumes: Task 2 (akcje, selektory, `FileRegistry`), `toUserMessage` (`core/api-error.ts`).
- Produces: `BATCH_CONCURRENCY = 2`; `type ConvertFileFn = (file: File) => Observable<unknown>`; `CONVERT_FILE = new InjectionToken<ConvertFileFn>('CONVERT_FILE')`; `mockConvertFile: ConvertFileFn` (+ `provideMockConvertFile(): Provider`); `ImportQueueEffects` z `schedule$` i `convert$`.

- [ ] **Step 1: Write failing specs** – `convert-file.mock.spec.ts` (`vi.useFakeTimers()`): `resolves a reference form after delay` (wynik ma `title` i `tabs`, nie wcześniej niż po 1500 ms), `alternates reference forms`, `fails with LLM_UNAVAILABLE for blad in name` (`Formularz_BLAD.pdf` → `HttpErrorResponse` status 503, `error.code === 'LLM_UNAVAILABLE'`). `import-queue.effects.spec.ts` (`provideMockActions`, `provideMockStore`): `schedule starts up to two pending` (3 pending, 0 processing → dokładnie 2× `convertStarted` w kolejności), `schedule starts next after success` (1 processing + 2 pending → 1× `convertStarted`), `removed pending is never started` (stan bez tego id → brak startu), `retry triggers schedule`, `convert succeeds` (`CONVERT_FILE` mock zwracający `of({ ok: 1 })` → `convertSucceeded` z `durationMs >= 0`), `convert fails with user message` (`throwError(HttpErrorResponse 503 LLM_UNAVAILABLE)` → `convertFailed` z komunikatem z Global Constraints), `missing file fails` (rejestr bez pliku → „Plik niedostępny – dodaj go ponownie”), `success releases file from registry`. `import-queue.integration.spec.ts` (prawdziwy `provideStore`/`provideEffects`, `CONVERT_FILE` = `timer(1000).pipe(map(() => ({})))`, fałszywe timery): `never more than two processing` (10 plików; po każdym `advanceTimersByTime(100)` sprawdzaj `selectQueueCounts().processing <= 2`; na końcu `done === 10`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `schedule$`: `ofType(filesAdded, convertSucceeded, convertFailed, retry, removed)` → `withLatestFrom(store.select(selectQueueItems))` → policz `processing`, weź pierwsze `pending` do wolnych slotów → `from([...convertStarted])`. `convert$`: `ofType(convertStarted)` → `mergeMap` → plik z rejestru (brak → `convertFailed`) → `inject(CONVERT_FILE)(file)` → `map(convertSucceeded)` / `catchError(convertFailed z toUserMessage dla HttpErrorResponse, inaczej „Wystąpił nieoczekiwany błąd”)`; po sukcesie `registry.delete(id)`. Mock: `defer(() => timer(1500 + Math.random()*2500))` → `switchMap(() => from(import('./mock-forms/…json')))`, przełączanie licznikiem modułowym.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(import): add queue scheduler, conversion effect and mock converter`

### Task 4: ZIP i pobieranie plików

**Files:**
- Create: `frontend/src/app/features/import/zip-results.ts`, `zip-results.spec.ts`, `frontend/src/app/features/import/download.ts`
- Modify: `frontend/package.json`, `package-lock.json` (`npm install fflate@^0.8.3`)

**Interfaces:**
- Produces: `resultFileName(name: string): string` (bez ostatniego rozszerzenia + `.json`); `buildResultsZip(items: { name: string; result: unknown }[]): Blob`; `downloadBlob(blob: Blob, fileName: string): void` (tymczasowy `<a download>`, `URL.revokeObjectURL` po kliknięciu); `downloadJson(result: unknown, fileName: string): void`.

- [ ] **Step 1: Write failing specs** – `resultFileName('Deklaracja.docx') === 'Deklaracja.json'`, `resultFileName('a.b.pdf') === 'a.b.json'`; `zip contains pretty JSON` (`unzipSync` → `strFromU8` → `JSON.parse` równe wejściu, tekst zawiera `\n  `); `dedupes names` (dwa `wniosek.pdf` + `wniosek.png` → `wniosek.json`, `wniosek (2).json`, `wniosek (3).json`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`zipSync`, `strToU8`; `Blob` typu `application/zip`).
- [ ] **Step 4: Run** → PASS; sprawdź licencję `npx license-checker --packages fflate@0.8.3` albo `npm view fflate license` → MIT.
- [ ] **Step 5: Commit** `feat(import): zip and download conversion results`

### Task 5: Ekran importu i podpięcie w aplikacji

**Files:**
- Modify: `frontend/src/app/features/import/import-page.ts` (+ create `import-page.html`), `frontend/src/app/app.config.ts`, `frontend/src/app/app.routes.ts` (bez zmian trasy `/import`, jeśli tytuł już jest)
- Create: `frontend/src/app/features/import/import-page.stories.ts`

**Interfaces:**
- Consumes: Task 1–4; `app-file-drop` (`filesSelected: File[]`, `maxSizeMb`), `app-card`, `table[appTable]`, `app-badge`, `app-progress`, `button[appButton]`.
- Produces: `ImportPage` (ten sam selektor `app-import-page`).

- [ ] **Step 1: Write failing stories** (`Ekrany/Import`, `provideMockStore`, mock `FileRegistry`): `Empty` → tekst „Kolejka jest pusta. Dodaj pliki powyżej.”, „Pobierz wszystkie (ZIP)” `disabled`; `Mixed` (4 pozycje: done 12 s, processing, pending, error `retryable:false` „Nieobsługiwane rozszerzenie…”) → licznik „4 pliki · 1 gotowy · 1 błąd”, tabela `aria-labelledby` wskazuje nagłówek „Kolejka”, wiersz błędu: tylko przycisk `Usuń formularz.jpe` z `toHaveAccessibleDescription(/Nieobsługiwane/)` (brak „Ponów”), wiersz done: `Otwórz wynik …` jako link do `/result/<id>`; `RetryableError` (error `retryable:true`) → przycisk „Ponów …” dispatchuje `retry({id})`; `AddFiles` → upload 2 plików (jeden `a.exe`) przez input w `app-file-drop` → dispatch `filesAdded` z 2 pozycjami, druga `status:'error'`, `retryable:false`; `scrollWidth <= clientWidth` karty przy długiej nazwie bez spacji. a11y w motywie `tool`.
- [ ] **Step 2: Run** `npm run test:storybook` → FAIL.
- [ ] **Step 3: Implement.** `app.config.ts`: dopisz `[importQueueFeatureKey]: importQueueReducer` do mapy `provideStore`, `ImportQueueEffects` do `provideEffects`, `provideMockConvertFile()`. `ImportPage`: `onFiles(files)` → dla każdego `id = crypto.randomUUID()`, `validateFile`, `registry.add` tylko dla poprawnych, `filesAdded`. Szablon wg spec (kolumny `w-px whitespace-nowrap` poza „Plik”, nazwa `[overflow-wrap:anywhere]`, `aria-describedby` przycisków → id błędu). Region `aria-live="polite"` (`sr-only`) z komunikatem przy przejściu statusu na `done`/`error` (porównanie z poprzednim stanem w `effect`). Nasłuch `window:dragover`/`window:drop` z `preventDefault` (host listeners komponentu strony) i `window:beforeunload` ustawiający `returnValue`, gdy `processing + pending > 0`. „Usuń” → `removed` + `registry.delete`.
- [ ] **Step 4: Run** wszystkie testy i `npx ng build` → PASS; w wyniku buildu dane mocka w osobnym chunku (initial < 500 kB).
- [ ] **Step 5: Commit** `feat(import): add import page with file queue`

### Task 6: Ekran wyniku

**Files:**
- Create: `frontend/src/app/features/result/result-page.ts` (+ `.html`), `result-page.stories.ts`
- Delete: `frontend/src/app/features/result/.gitkeep`
- Modify: `frontend/src/app/app.routes.ts` (`{ path: 'result/:id', title: 'Wynik', canActivate: [authGuard], loadComponent: … }` przed `**`)

**Interfaces:**
- Consumes: `selectQueueItem(id)`, `resultFileName`, `downloadJson` (Task 2, 4).
- Produces: `ResultPage`.

- [ ] **Step 1: Write failing stories** (`Ekrany/Wynik`, `provideMockStore`, router z `id`): `Done` → nagłówek z nazwą pliku, `<pre>` z tekstem zawierającym `"title"`, przycisk „Pobierz .json”, link „← Wróć do importu” do `/import`, `<pre>` ma `tabindex="0"` i `aria-label="Wynik konwersji w formacie JSON"`; `Unavailable` (nieznane id) → „Wynik niedostępny. Wróć do importu i przetwórz plik ponownie.” z linkiem.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (id z `input()` przez `withComponentInputBinding()` w `provideRouter`, jeśli nie ma – dodaj w `app.config.ts`; inaczej `ActivatedRoute`).
- [ ] **Step 4: Run** wszystkie testy i build → PASS.
- [ ] **Step 5: Commit** `feat(import): add conversion result page`
