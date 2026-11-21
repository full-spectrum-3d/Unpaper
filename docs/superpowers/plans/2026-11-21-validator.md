# Ekran „Walidator”: plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ekran `/validator`: wklejenie albo wgranie JSON-a formularza, sprawdzenie składni na kliencie, `POST /forms/validate`, lista błędów i ostrzeżeń z „Pokaż w JSON”. Do tego wejście z ekranu wyniku.

**Architecture:** Widok JSON z podświetleniem zostaje wydzielony z `result-page` do `app-json-view` (wejścia `lines`, `highlight`, `label`, metoda `reveal()`). Czyste funkcje `parseJsonInput` i `readJsonFile` obsługują wejście. `ValidatorPage` woła wygenerowany `FormsService`, czyta wynik defensywnie i opcjonalnie bierze formularz z kolejki po `?item=<id>`.

**Tech Stack:** Angular 22 (zoneless, sygnały, `withComponentInputBinding`), NgRx (odczyt), Tailwind 4 z tokenami, Vitest (jsdom), Storybook 10 + a11y.

**Spec:** `docs/superpowers/specs/2026-11-21-validator-design.md` (z sekcją „Doprecyzowania”).

## Global Constraints

- Bez nowych zależności npm. Angular: `input()/output()`, `inject()`, natywny control flow, `host: {}`, bez jawnego `ChangeDetectionStrategy`.
- `app-file-drop` i ekran importu bez zmian.
- Copy (dokładnie):
  - nagłówki i etykiety:
    - `Walidator JSON`, opis `Sprawdź, czy JSON formularza spełnia reguły COI.`;
    - etykieta pola `JSON formularza`;
    - przyciski `Wgraj plik .json`, `Sprawdź` (w trakcie `Sprawdzanie…`);
    - menu `Walidator`, tytuł trasy `Walidator`;
  - błędy wejścia:
    - `Niepoprawny JSON: linia L, kolumna K.` / `Niepoprawny JSON.`;
    - `JSON musi być obiektem formularza (zaczynać się od {).`;
    - `Wgraj plik .json do 5 MB.`;
  - wynik:
    - h2 `Wynik`;
    - sukces `JSON spełnia reguły COI.`; niepowodzenie `Znaleziono N <błąd|błędy|błędów> i M <ostrzeżenie|ostrzeżenia|ostrzeżeń>.` (odmiana przez istniejące `pluralPl` z `features/import/format.ts`);
    - h3 `Błędy (N)`, `Ostrzeżenia (M)`, `Sformatowany JSON`; pusta lista `Brak`;
    - przycisk `Pokaż w JSON`, `aria-label="Pokaż w JSON: <kod>"`;
    - nieaktualny wynik: `JSON zmieniono po sprawdzeniu. Sprawdź ponownie.`;
  - serwer i wejście z wyniku:
    - 422 `Serwer odrzucił JSON jako niepoprawny.`, inne błędy przez `toUserMessage`;
    - przycisk na ekranie wyniku `Sprawdź w walidatorze`; brak wyniku w kolejce: `Nie znaleziono wyniku do sprawdzenia. Wklej JSON ręcznie.`;
  - etykiety regionów JSON: `Wynik konwersji w formacie JSON` (ekran wyniku), `Sprawdzany JSON` (walidator).
- Limit pliku 5 MB (5 * 1024 * 1024 bajtów), rozszerzenie `.json` (bez rozróżniania wielkości liter), jeden plik.
- Link „Pokaż w JSON” tylko, gdy `path` istnieje w `ranges` sformatowanego JSON-a; w przeciwnym razie ścieżka tekstem `text-fg-muted`.
- Testy: `cd frontend && source ~/.nvm/nvm.sh && nvm use >/dev/null && npx ng test --watch=false` i `npm run test:storybook` (a11y = error), każde w jednym wywołaniu powłoki; przed commitem ostatniego zadania `npx ng build`.
- Commity `typ(zakres): opis`, **bez** `Co-Authored-By`.

## Review Focus

1. JSON z BOM-em albo białymi znakami wokół (np. skopiowany z edytora) → parsuje się poprawnie. Test w Task 2.
2. Błąd składni w ostatniej linii lub po znaku nowej linii `\r\n` → linia i kolumna liczone poprawnie. Test w Task 2.
3. Odpowiedź serwera z polami złego typu (`errors: null`, wpis `null`, `path: 5`) → lista renderuje się z „Brak” lub bez tego wpisu, bez wyjątku. Test w Task 3.
4. Kliknięcie „Sprawdź” dwa razy szybko → jedno żądanie w locie (przycisk wyłączony), wynik nie miga. Test w Task 3.
5. Przejście z wyniku A do wyniku B (`?item` zmienia się na zamontowanej stronie) → pole i wynik dotyczą B. Test w Task 3.

---

### Task 1: Wspólny widok JSON

**Files:**
- Create: `frontend/src/app/features/result/json-view.ts`, `json-view.spec.ts`
- Modify: `frontend/src/app/features/result/result-page.ts`, `result-page.html`

**Interfaces:**
- Consumes: `JsonLines`, `formatJson` (`json-lines.ts`).
- Produces:
  ```ts
  // selector 'app-json-view'
  lines = input.required<JsonLines>();
  highlight = input<string | null>(null);
  label = input.required<string>();
  reveal(): void; // afterNextRender: pierwsza linia zakresu scrollIntoView?.({block:'center'}), fragment focus({preventScroll:true})
  ```

- [ ] **Step 1: Write failing tests** `json-view.spec.ts` (host z `formatJson(nadplata)`):
  - `textContent` regionu `role="region"` o nazwie `label` === `JSON.stringify(nadplata, null, 2)`, z podświetleniem i bez.
  - `highlight='tabs[0]'` → dokładnie jeden element `.bg-warning-subtle` z `role="group"` i `aria-label="Fragment JSON: tabs[0]"`, zawiera linie `data-line` od `start` do `end`. Zmiana `highlight` na inną ścieżkę → nadal jeden fragment, nowy zakres. `highlight` nieistniejący → brak fragmentu.
  - `reveal()` po ustawieniu `highlight` → fragment ma fokus, a `scrollIntoView` (spy na `Element.prototype`) wywołany na pierwszej linii zakresu z `{ block: 'center' }`.
- [ ] **Step 2:** Uruchom unit. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.** Przenieś z `result-page` computed `segments`, szablon `<pre>` (z komentarzem o białych znakach) i logikę fokusu do `JsonView`. `ResultPage`: `<app-json-view #jsonView [lines]="json()" [highlight]="highlightPath()" label="Wynik konwersji w formacie JSON" />`, a `onShowInJson` ustawia ścieżkę, zakładkę i woła `jsonView().reveal()` (`viewChild.required` albo `viewChild`).
- [ ] **Step 4:** Unit i `npm run test:storybook`: istniejące stories `Ekrany/Wynik` przechodzą bez zmiany asercji.
- [ ] **Step 5: Commit** `refactor(result): extract the JSON view into a shared component`

---

### Task 2: Wejście walidatora

**Files:**
- Create: `frontend/src/app/features/validator/json-input.ts`, `json-input.spec.ts`

**Interfaces:**
- Produces:
  ```ts
  export type ParseResult = { ok: true; value: Record<string, unknown> } | { ok: false; message: string };
  export function parseJsonInput(text: string): ParseResult;
  export const MAX_JSON_FILE_BYTES = 5 * 1024 * 1024;
  export function readJsonFile(file: File): Promise<{ ok: true; text: string } | { ok: false; message: string }>;
  ```

- [ ] **Step 1: Write failing tests**
  - `parseJsonInput('{"a":1}')` → ok z `{a:1}`; `'﻿  {"a":1}\n'` → ok.
  - `'[1]'`, `'"x"'`, `'null'`, `'5'` → `{ ok:false, message:'JSON musi być obiektem formularza (zaczynać się od {).' }`.
  - `'{\n  "a": 1,\n  "b": \n}'` → `Niepoprawny JSON: linia 3, kolumna 8.` (policz kolumnę od 1 w miejscu błędu zgłoszonym przez silnik; test ma użyć pozycji z `JSON.parse` i sprawdzić zgodność linii; kolumnę asercją na wyliczonej z pozycji wartości). Wariant z `\r\n` daje tę samą linię.
  - Gdy komunikat błędu nie zawiera pozycji (zasymuluj przez wydzieloną funkcję `positionToLineColumn(text, pos)` i `extractPosition(message)` zwracającą `null`) → `Niepoprawny JSON.`
  - `extractPosition` rozpoznaje `"... at position 17"` oraz `"... (line 3 column 8)"`.
  - `readJsonFile`: plik `a.JSON` z treścią → ok z tekstem; `a.txt` → `Wgraj plik .json do 5 MB.`; plik > 5 MB (np. `new File([new Uint8Array(MAX_JSON_FILE_BYTES + 1)], 'a.json')`) → ten sam komunikat.
- [ ] **Step 2:** Uruchom. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.** BOM i białe znaki: `text.replace(/^﻿/, '').trim()`. Linia i kolumna z pozycji: liczenie `\n` w `text.slice(0, pos)` (po zdjęciu BOM, przed trim — użyj tej samej wersji tekstu, którą parsujesz). `readJsonFile` przez `file.text()`.
- [ ] **Step 4:** Uruchom. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(validator): parse JSON input and read .json files`

---

### Task 3: Ekran walidatora, trasa, menu i wejście z wyniku

**Files:**
- Create: `frontend/src/app/features/validator/validator-page.ts`, `validator-page.html`, `validator-page.spec.ts`, `validator-page.stories.ts` (`Ekrany/Walidator`)
- Modify: `frontend/src/app/app.routes.ts`, `frontend/src/app/app.html`, `frontend/src/app/features/result/result-page.html` (+ story, jeśli asercje dotyczą przycisków karty)

**Interfaces:**
- Consumes: `JsonView` (Task 1), `parseJsonInput`, `readJsonFile` (Task 2), `formatJson`, `FormsService.validateApiV1FormsValidatePost({ body })` (`shared/api/services/forms.service.ts`), `selectQueueItem(id)` (`store/import-queue/import-queue.selectors.ts`), `toUserMessage`, `pluralPl`.
- Produces: `ValidatorPage` z `item = input<string>()` (query param przez `withComponentInputBinding`). Trasa `{ path: 'validator', title: 'Walidator', canActivate: [authGuard], loadComponent: … }` przed `**`.

- [ ] **Step 1: Write failing tests** `validator-page.spec.ts` (TestBed: `provideHttpClient`, `provideHttpClientTesting`, `provideApiConfiguration('')`, `provideMockStore`, `provideRouter([])`):
  - Pusty tekst → `Sprawdź` wyłączony.
  - Tekst `{"a":` → klik `Sprawdź` → brak żądania (`expectNone`), widoczny komunikat `Niepoprawny JSON…`, pole ma `aria-invalid="true"` i `aria-describedby` na komunikat, fokus na polu.
  - Poprawny JSON → jedno `POST /api/v1/forms/validate` z ciałem = obiekt. W trakcie przycisk ma tekst `Sprawdzanie…` i jest wyłączony; drugi klik nie robi drugiego żądania.
  - Flush `{ valid: true, errors: [], warnings: [] }` → `role="status"` zawiera `JSON spełnia reguły COI.`, fokus na h2 `Wynik`.
  - Flush `{ valid: false, errors: [{code:'R06_REQUIREDNESS', message:'m', path:'tabs[0]'}, {code:'R01_SCHEMA', message:'n', path:'nie.ma'}], warnings: [{code:'W02_LABEL_TOO_LONG', message:'w'}] }` dla JSON-a z `tabs` → status `Znaleziono 2 błędy i 1 ostrzeżenie.`; `Błędy (2)`, `Ostrzeżenia (1)`; przycisk `Pokaż w JSON: R06_REQUIREDNESS` tylko dla pierwszego; tekst `nie.ma` przy drugim; klik → fragment `Fragment JSON: tabs[0]` ma fokus.
  - Flush `{ valid: false, errors: null, warnings: [null, {code: 5}] }` → `Błędy (0)`, `Brak`, bez wyjątku.
  - Zmiana tekstu po sprawdzeniu → `JSON zmieniono po sprawdzeniu. Sprawdź ponownie.`; `app-json-view` nadal pokazuje JSON z chwili sprawdzenia.
  - Flush błędu 422 → `role="alert"` z `Serwer odrzucił JSON jako niepoprawny.`; 500 z `{code:'X', detail:'d'}` → `role="alert"` z `d`; poprzedni wynik znika.
  - `item='d1'` przy stanie z wierszem `done` (`result: {title:'T', tabs: []}`) → pole zawiera `JSON.stringify(result, null, 2)` i od razu jedno żądanie. Zmiana `item` na `d2` (inny wiersz) → pole z `d2` i nowe żądanie. `item='nope'` → komunikat `Nie znaleziono wyniku do sprawdzenia. Wklej JSON ręcznie.` i brak żądania.
  - Wgranie pliku (zdarzenie `change` na ukrytym inpucie z `File`) → tekst w polu; zły plik → `Wgraj plik .json do 5 MB.`
- [ ] **Step 2:** Uruchom. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.**
  - Stan: `text`, `checking`, `checkedText`, `checkedLines` (`formatJson` obiektu z chwili sprawdzenia), `result` (znormalizowany: `valid: boolean`, `errors`/`warnings` jako tablice `{code, message, path?}` z pominięciem wpisów niebędących obiektami i pól niebędących stringami), `inputError`, `httpError`, `highlight`, `missingItem`.
  - `stale = computed(() => result() !== null && text() !== checkedText())`.
  - Efekt na `item()` (i wiersz z kolejki): ustawia tekst i woła `check()`, albo ustawia `missingItem`.
  - Plik: przycisk `appButton variant="secondary"` klika ukryty `input type="file" accept=".json,application/json"`.
  - `textarea` z klasami jak pole tekstowe (`border border-border-input rounded-field px-field-x py-field-y bg-surface text-fg font-mono focus-ring w-full`), 16 wierszy, `spellcheck="false"`.
  - Lista błędów jak w raporcie (kod `font-mono`), `app-json-view label="Sprawdzany JSON"`, `reveal()` po kliknięciu „Pokaż w JSON”.
  - `app.html`: druga pozycja menu `Walidator`. `result-page.html`: obok „Pobierz .json” link-przycisk `Sprawdź w walidatorze` (`routerLink="/validator"`, `[queryParams]="{ item: i.id }"`, klasy jak link „Otwórz wynik” w imporcie).
  - Story `Ekrany/Walidator`: `Pusty`, `ZBledami` (mock `FormsService` przez provider z `of(...)`), `Poprawny`, `BladSkladni`.
- [ ] **Step 4:** Unit, `npm run test:storybook`, `npx ng build`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(validator): add the validator screen with links into the JSON`
