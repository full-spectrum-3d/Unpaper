# Zakładka „Raport” na ekranie wyniku: plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ekran wyniku ma trzy zakładki (Podgląd / JSON / Raport). Raport konwersji z backendu pokazuje ostrzeżenia, poprawki, słowniki, statystyki i przebieg, a „Pokaż w JSON” skacze do podświetlonego fragmentu JSON-a.

**Architecture:** `ConvertFileFn` zwraca `{ form, report }`, a wiersz kolejki trzyma `report` obok `result` (formularza). Czysty formatter `formatJson` daje linie identyczne ze `JSON.stringify(…, 2)` i mapę ścieżka → zakres linii. `ReportView` emituje `showInJson(path)`, a `ResultPage` przełącza zakładkę, podświetla zakres i ustawia na nim fokus.

**Tech Stack:** Angular 22 (zoneless, sygnały), NgRx, Tailwind 4 z tokenami, Vitest (jsdom), Storybook 10 + a11y.

**Spec:** `docs/superpowers/specs/2026-11-21-result-report-design.md` (z sekcją „Doprecyzowania”).

## Global Constraints

- Bez nowych zależności npm. Angular: `input()/output()`, `inject()`, natywny control flow, `host: {}`, bez jawnego `ChangeDetectionStrategy`.
- ZIP i „Pobierz .json” zawierają dalej sam formularz (`QueueItem.result`). Raport nie trafia do plików.
- Link „Pokaż w JSON” tylko gdy: ścieżka zaczyna się od `tabs[`, istnieje dokładnie w `ranges` i kod ≠ `R03_EMPTY_PAGE`.
- Copy (dokładnie):
  - zakładki: `Podgląd formularza`, `JSON`, `Raport` (tablist `aria-label="Widok wyniku"`);
  - sekcje h2: `Ostrzeżenia (N)`, `Poprawki autonaprawy (N)`, `Propozycje słowników (N)`, `Statystyki`, `Przetwarzanie`;
  - pusta lista: `Brak`; brak raportu: `Raport niedostępny dla tego wyniku.`;
  - przycisk: `Pokaż w JSON`, `aria-label="Pokaż w JSON: <kod>"`;
  - dopiski ścieżek: `(miejsce w szkicu, nie w wyniku)` dla ścieżek nie zaczynających się od `tabs[` i `(element nie występuje w wyniku)` dla `tabs[…]` bez zakresu lub z kodem `R03_EMPTY_PAGE`;
  - etykiety metod: `pdf_text` → `tekst z PDF`, `ocr` → `OCR`, `docx` → `DOCX`, `xlsx` → `XLSX`;
  - etapy: `normalizeMs` → `normalizacja`, `extractMs` → `ekstrakcja`, `analyzeMs` → `analiza`, `buildMs` → `budowa`;
  - czas w sekundach z jedną cyfrą po przecinku: `25,1 s`;
  - fallback: `szkic regułowy (bez LLM)`.
- Testy: `cd frontend && source ~/.nvm/nvm.sh && nvm use >/dev/null && npx ng test --watch=false` i `npm run test:storybook` (a11y = error), każde w jednym wywołaniu powłoki.
- Commity `typ(zakres): opis`, **bez** `Co-Authored-By`.

## Review Focus

1. Raport z polami złego typu (np. `warnings: "x"`, `stats: null`, brak `timings`) → widok renderuje się z „Brak” i bez wyjątków. Test w Task 3.
2. Odpowiedź HTTP bez klucza `form` (starszy backend) → cała odpowiedź jest formularzem, `report = null`. Test w Task 1.
3. JSON z kluczami zawierającymi znaki specjalne i z pustymi `{}`/`[]` → linie identyczne ze `stringify`. Test w Task 2.
4. „Pokaż w JSON” dwa razy w różne ścieżki → podświetlony tylko ostatni zakres, fokus na nim. Test w Task 4.
5. Przejście Raport → Podgląd zachowuje wpisaną odpowiedź i bieżący krok podglądu. Test w Task 4.

---

### Task 1: Raport w danych konwersji i kolejce

**Files:**
- Modify: `frontend/src/app/features/import/convert-file.ts`, `convert-file.http.ts`, `convert-file.http.spec.ts`, `convert-file.mock.ts`, `convert-file.mock.spec.ts`
- Create: `frontend/src/app/features/import/mock-report.ts`
- Modify: `frontend/src/app/store/import-queue/import-queue.reducer.ts`, `import-queue.actions.ts`, `import-queue.effects.ts` (+ specy), `frontend/src/app/features/import/import-page.ts` (`report: null` przy dodawaniu)
- Modify: fixture'y `QueueItem` w specach i stories (`grep -rln "retryable" frontend/src`)

**Interfaces:**
- Produces:
  ```ts
  // convert-file.ts
  export interface ConvertResult { form: unknown; report: unknown | null }
  export type ConvertFileFn = (file: File, password?: string) => Observable<ConvertResult>;
  // reducer
  QueueItem.report: unknown | null;           // wymagane pole
  // actions
  convertSucceeded: props<{ id: string; result: unknown; report: unknown | null; durationMs: number }>()
  // mock-report.ts
  export function mockReport(form: unknown): unknown; // raport pasujący do danego mocka
  ```

- [ ] **Step 1: Write failing tests**
  - HTTP: żądanie ma parametr `report=true` (`req.request.params.get('report') === 'true'` albo URL zawiera `report=true`). Flush `{ form: {title:'F'}, report: {durationMs: 1} }` → `{ form: {title:'F'}, report: {durationMs:1} }`. Flush `{ title: 'F' }` (bez `form`) → `{ form: {title:'F'}, report: null }`.
  - Mock: wynik ma `form.title` i `report` z `warnings` (≥1 ze ścieżką `tabs[…]` istniejącą w danym formularzu i 1 ze ścieżką `subject_pages[0].sections[0].fields[0]`), `fixes` (≥1 ze ścieżką `tabs[…]` istniejącą w formularzu), `dictionaryProposals` (1, z `usedBy`), `stats`, `extraction.method: 'pdf_text'`, `llm.model`, `timings`, `durationMs`. Sprawdź istnienie ścieżki przez proste chodzenie po obiekcie w teście.
  - Effects: `convertSucceeded` ma `result` = `form` i `report` z wyniku convert. Reducer: `convertSucceeded` zapisuje `report`.
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.** HTTP rozpakowuje: `body && typeof body === 'object' && 'form' in body ? { form: body.form, report: body.report ?? null } : { form: body, report: null }`. Mock tworzy raport przez `mockReport(form)` (ścieżki wybierz z realnej struktury mocka, np. `tabs[0].questions[1]` i `tabs[1].questions[0].field.repeatingSectionGrid[1]`, ale zweryfikuj w danych). Kod-komunikat poprawki np. `R12_DUPLICATE_TECH_NAME` „Zmieniono techName na kwota_2”, ostrzeżenia np. `W12_LOW_OCR_CONFIDENCE` i `W07_CHOICE_OPTIONS`.
- [ ] **Step 4:** Uruchom unit i `npm run test:storybook`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(import): request and keep the conversion report`

---

### Task 2: Formatter JSON z mapą ścieżek

**Files:**
- Create: `frontend/src/app/features/result/json-lines.ts`, `json-lines.spec.ts`

**Interfaces:**
- Produces:
  ```ts
  export interface LineRange { start: number; end: number } // 0-based, włącznie
  export interface JsonLines { lines: string[]; ranges: ReadonlyMap<string, LineRange> }
  export function formatJson(value: unknown): JsonLines;
  ```

- [ ] **Step 1: Write failing tests**
  - Dla `nadplata-podatku.json`: `formatJson(x).lines.join('\n') === JSON.stringify(x, null, 2)`. To samo dla `{ "a.b": [1, {}, []], "q\"": null, e: {} }`.
  - `ranges.get('title')` → `{ start: 1, end: 1 }` dla `{ title: 'T', tabs: [...] }`.
  - Dla mocka: `ranges.get('tabs[0]')` istnieje, `start` wskazuje linię `    {`, a `end` linię `    }` lub `    },`. `ranges.get('tabs[0].questions[1]')` zawiera się w zakresie `tabs[0]`. `ranges.get('tabs[0].questions[0].field.repeatingSectionGrid[0]')` istnieje (dobierz indeksy z danych). `ranges.has('tabs[99]') === false`.
  - Wartość `[]` i `{}` ma `start === end`.
- [ ] **Step 2:** Uruchom. Oczekiwane: FAIL.
- [ ] **Step 3: Implement** rekurencyjnie: kluczem jest ścieżka rodzica + `.key` (lub `key` na najwyższym poziomie) albo `[i]`; zakres liczony od linii z kluczem/otwarciem do linii zamknięcia. Prymitywy (`string`, `number`, `boolean`, `null`) przez `JSON.stringify`.
- [ ] **Step 4:** Uruchom. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(result): format JSON with a path-to-line map`

---

### Task 3: Widok raportu

**Files:**
- Create: `frontend/src/app/features/result/report.ts`, `report.spec.ts`
- Create: `frontend/src/app/features/result/report-view.ts`, `report-view.spec.ts`, `report-view.stories.ts` (`Wynik/Raport`)

**Interfaces:**
- Consumes: `LineRange` (Task 2), `mockReport` (Task 1) w story.
- Produces:
  ```ts
  // report.ts — typy ReportIssue i ConversionReport jak w spec
  export function asReport(value: unknown): ConversionReport | null;
  export type PathTarget = { kind: 'link' } | { kind: 'draft' } | { kind: 'missing' } | { kind: 'none' };
  export function pathTarget(issue: ReportIssue, ranges: ReadonlyMap<string, LineRange>): PathTarget;
  export function formatSeconds(ms: number): string; // 25110 → '25,1 s'
  // report-view.ts — selector 'app-report-view'
  report = input.required<ConversionReport | null>();
  ranges = input.required<ReadonlyMap<string, LineRange>>();
  showInJson = output<string>(); // ścieżka
  ```

- [ ] **Step 1: Write failing tests**
  - `asReport`: obiekt → ten sam obiekt z tablicami `warnings/fixes/dictionaryProposals` zawsze jako tablice (zły typ → `[]`); `null`, `'x'`, `[]` → `null`.
  - `pathTarget`: bez `path` → `none`; `subject_pages[0].sections[0].fields[0]` → `draft`; `title` → `draft`; `tabs[0]` obecne w ranges → `link`; `tabs[9]` nieobecne → `missing`; `R03_EMPTY_PAGE` z `tabs[0]` obecnym → `missing`.
  - `formatSeconds(25110) === '25,1 s'`, `formatSeconds(140) === '0,1 s'`, `formatSeconds(0) === '0,0 s'`.
  - `ReportView` (raport z `mockReport` i ranges z `formatJson(form)`):
    - h2 w kolejności `Ostrzeżenia (N)`, `Poprawki autonaprawy (N)`, `Propozycje słowników (1)`, `Statystyki`, `Przetwarzanie`;
    - przycisk `Pokaż w JSON: <kod>` dla pozycji `link`, klik emituje ścieżkę;
    - pozycja `draft` ma tekst ścieżki i `(miejsce w szkicu, nie w wyniku)` bez przycisku;
    - słownik: nazwa, `Używa: …`, liczba pozycji;
    - `Przetwarzanie` zawiera `tekst z PDF`, model, `analiza` z sekundami;
    - przy `llm.fallback: true` jest `szkic regułowy (bez LLM)`.
  - Raport `{ warnings: 'x', stats: null }` → sekcje z `Brak`, bez wyjątku. `report = null` → `Raport niedostępny dla tego wyniku.`
- [ ] **Step 2:** Uruchom. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.** Listy jako `<ul>`, statystyki i przetwarzanie jako `<dl>`, kody `font-mono`, nagłówki `text-section-title font-semibold`. Story `Wynik/Raport`: `ZRaportem`, `BezRaportu`, `ZFallbackiem`.
- [ ] **Step 4:** Unit i `npm run test:storybook`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(result): add the conversion report view`

---

### Task 4: Zakładki i skok do JSON-a na ekranie wyniku

**Files:**
- Modify: `frontend/src/app/features/result/result-page.ts`, `result-page.html`, `result-page.stories.ts`
- Create: `frontend/src/app/features/result/result-page.spec.ts` (jeśli prościej niż w story; oba dopuszczalne)

**Interfaces:**
- Consumes: `formatJson`, `LineRange` (Task 2); `ReportView`, `asReport` (Task 3); `QueueItem.report` (Task 1).
- Produces: `ResultPage` z `activeTab = signal<'preview' | 'json' | 'report'>`, `highlightPath = signal<string | null>`.

- [ ] **Step 1: Write failing tests**
  - Tablist `Widok wyniku` z 3 zakładkami dla formularza; domyślnie `Podgląd formularza` ma `aria-selected="true"`. `ArrowRight` z Podglądu → JSON aktywny i ma fokus, `End` → Raport, `Home` → Podgląd, `ArrowLeft` z Podglądu → Raport (zawijanie). Każda zakładka ma `aria-controls` panelu z `role="tabpanel"` i `aria-labelledby`.
  - Wynik nie-formularz: brak zakładki Podgląd, domyślnie JSON, Raport dostępny.
  - Raport → klik `Pokaż w JSON: <kod>` → JSON aktywny. Element zakresu (`aria-label="Fragment JSON: <ścieżka>"`) ma fokus i zawiera linie z `data-line` od `start` do `end` z klasą `bg-warning-subtle`. Drugi klik innej pozycji → podświetlony tylko nowy zakres.
  - Wpisanie wartości w pole podglądu → Raport → Podgląd → wartość zachowana.
  - Tekst JSON w zakładce (`textContent` regionu bez podświetlenia) równy `JSON.stringify(result, null, 2)`.
- [ ] **Step 2:** Uruchom. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.**
  - `computed`: `report = asReport(item()?.report)`, `json = formatJson(item()?.result)`.
  - Widok JSON: `<pre role="region" aria-label="Wynik konwersji w formacie JSON" tabindex="0">`. Linie poza zakresem jako tekst. Zakres jako `<span tabindex="-1" aria-label="Fragment JSON: …" class="block bg-warning-subtle">` z liniami `data-line`.
  - `onShowInJson(path)`: `highlightPath.set(path)`, `activeTab.set('json')`, `afterNextRender` → `scrollIntoView({block:'center'})?.` i `focus()` zakresu.
  - Opuszczenie zakładki JSON czyści `highlightPath`.
  - Panel podglądu zostaje w DOM z `[hidden]`.
  - Usuń stary przełącznik `aria-pressed`.
  - Story `Ekrany/Wynik`: dodaj wariant z `report: mockReport(nadplata)`. Istniejące stories dostosuj do zakładek.
- [ ] **Step 4:** Unit i `npm run test:storybook`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(result): add report tab and jump from report to JSON`
