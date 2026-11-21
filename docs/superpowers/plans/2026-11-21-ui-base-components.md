# Komponenty bazowe UI (ekran importu) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Siedem komponentów bazowych (button, table, badge, progress, card, topbar, file-drop) i story kompozycji kolejki w Storybooku, na tokenach semantycznych, z play testami i a11y w trybie `error`.

**Architecture:** Standalone komponenty Angular 22 w `src/app/shared/ui/<nazwa>/`, `OnPush`, inputy przez `input()` / `input.required()`, outputy przez `output()`. Natywne elementy przez selektory atrybutowe (`button[appButton]`, `table[appTable]`), klasy na hoście przez `host: { class, '[class]' }`. Testy to play functions w `*.stories.ts`, uruchamiane przez `npm run test:storybook` (Vitest + Playwright, addon a11y w trybie `error`).

**Tech Stack:** Angular 22, Tailwind CSS 4, Storybook 10.6 (`@storybook/angular-vite`, `storybook/test`: `expect`, `fn`, `userEvent`, `within`, `fireEvent`).

**Spec:** `docs/superpowers/specs/2026-11-21-ui-base-components-design.md` (tokeny: `docs/superpowers/specs/2026-11-21-design-tokens-design.md`, wartości w `frontend/src/styles/tokens.css`).

## Global Constraints

- Polecenia w `frontend/` po `source ~/.nvm/nvm.sh && nvm use`. Test: `npm run test:storybook`. Wszystkie testy (także stare) muszą przechodzić.
- Tylko klasy semantyczne (`bg-surface`, `text-fg`, `border-border`, `rounded-card`…). Żadnych hexów ani domyślnej palety Tailwind (i tak jest wyłączona).
- Elementy interaktywne dostają klasę `focus-ring` (utility z `tokens.css`).
- Status nigdy tylko kolorem: zawsze ikona `aria-hidden="true"` + tekst.
- Żadnych nowych zależności.
- Każdy plik stories eksportuje też story z `globals: { theme: 'preview' }`, żeby a11y sprawdził oba motywy.
- Tytuły stories: `UI/<Nazwa>`; teksty UI po polsku.
- Commity bez linii `Co-Authored-By`.

## Review Focus

1. **Ten sam plik wybrany drugi raz** musi znów wyemitować `filesSelected` (input trzeba zresetować) → test `re-selecting the same file emits again` w Task 4.
2. **Upuszczenie czegoś, co nie jest plikiem** (zaznaczony tekst, pusta lista) nie może emitować pustej tablicy → test `drop without files emits nothing` w Task 4.
3. **Bardzo długa nazwa pliku** bez spacji nie może rozpychać tabeli poza kartę → test `long file name does not overflow card` w Task 5.
4. **Wyłączony przycisk** nie może wywołać akcji → test `disabled button does not fire click` w Task 1.
5. **Status czytelny bez koloru** (czytnik ekranu, druk w skali szarości) → test `each status has visible text label` w Task 2.

---

### Task 1: `button[appButton]` i `table[appTable]`

**Files:**
- Create: `frontend/src/app/shared/ui/button/button.ts`, `frontend/src/app/shared/ui/button/button.stories.ts`
- Create: `frontend/src/app/shared/ui/table/table.ts`, `frontend/src/app/shared/ui/table/table.stories.ts`

**Interfaces:**
- Produces: `Button` (selector `button[appButton]`, `variant = input<'primary' | 'secondary' | 'ghost'>('secondary')`, template `<ng-content />`); `Table` (selector `table[appTable]`, bez inputów, style `th`/`td` przez arbitralne warianty `[&_th]:…`, `[&_td]:…`).

- [ ] **Step 1: Write failing stories** – `button.stories.ts`: harness z trzema przyciskami (`Zapisz` primary, `Anuluj` secondary, `Usuń` ghost) i `<button appButton disabled (click)="clicked()">Wyłączony</button>`, gdzie `clicked` to `fn()` w args.

```ts
// variants use semantic colors
expect(css(c.getByRole('button', { name: 'Zapisz' })).backgroundColor).toBe('rgb(0, 82, 165)');
expect(css(c.getByRole('button', { name: 'Zapisz' })).color).toBe('rgb(255, 255, 255)');
expect(css(c.getByRole('button', { name: 'Anuluj' })).backgroundColor).toBe('rgb(255, 255, 255)');
expect(css(c.getByRole('button', { name: 'Anuluj' })).borderColor).toBe('rgb(0, 82, 165)');
expect(css(c.getByRole('button', { name: 'Usuń' })).backgroundColor).toBe('rgba(0, 0, 0, 0)');
expect(css(c.getByRole('button', { name: 'Zapisz' })).borderRadius).toBe('4px');
// disabled button does not fire click
await userEvent.click(c.getByRole('button', { name: 'Wyłączony' }), { pointerEventsCheck: 0 });
expect(args.clicked).not.toHaveBeenCalled();
// focus ring
await userEvent.tab();
expect(css(document.activeElement as HTMLElement).outlineWidth).toBe('3px');
```

`table.stories.ts`: tabela z nagłówkami `Plik`, `Status` i jednym wierszem.

```ts
expect(css(c.getByRole('columnheader', { name: 'Plik' })).color).toBe('rgb(91, 100, 112)');
expect(css(c.getByRole('cell', { name: /deklaracja/ })).borderBottomColor).toBe('rgb(213, 219, 226)');
expect(css(c.getByRole('table')).width).toBe(css(c.getByRole('table').parentElement!).width);
```

- [ ] **Step 2: Run** `npm run test:storybook` → FAIL (brak modułów `./button`, `./table`).
- [ ] **Step 3: Implement `Button` i `Table`.** Button: `primary` = `bg-primary text-on-primary border-primary hover:bg-primary-hover`, `secondary` = `bg-surface text-primary border-primary hover:bg-primary-subtle`, `ghost` = `bg-transparent text-primary border-transparent hover:bg-primary-subtle`; wspólne `border rounded-field px-[12px] py-field-y font-semibold text-body focus-ring disabled:opacity-50 disabled:cursor-not-allowed`. Table: `w-full border-collapse text-body`, `th`: `text-left font-semibold text-fg-muted border-b border-border`, `td`: `border-b border-border align-middle`, padding `py-[7px] px-[10px]`, ostatni wiersz bez obramowania.
- [ ] **Step 4: Run** `npm run test:storybook` → PASS.
- [ ] **Step 5: Commit** `feat(ui): add button and table base components`

### Task 2: `app-badge` i `app-progress`

**Files:**
- Create: `frontend/src/app/shared/ui/badge/badge.ts`, `badge.stories.ts`
- Create: `frontend/src/app/shared/ui/progress/progress.ts`, `progress.stories.ts`

**Interfaces:**
- Produces: `export type FileStatus = 'pending' | 'processing' | 'done' | 'error'` (eksport z `badge.ts`); `Badge` (`app-badge`, `status = input.required<FileStatus>()`); `Progress` (`app-progress`, `label = input.required<string>()`).

- [ ] **Step 1: Write failing stories.** Badge: harness z czterema badge'ami.

```ts
// each status has visible text label
for (const t of ['Oczekuje', 'Przetwarzanie', 'Gotowe', 'Błąd']) expect(c.getByText(t)).toBeVisible();
const done = c.getByText('Gotowe').closest('app-badge')!;
expect(css(done).backgroundColor).toBe('rgb(230, 244, 234)');
expect(css(done).color).toBe('rgb(19, 108, 46)');
expect(css(c.getByText('Błąd').closest('app-badge')!).color).toBe('rgb(179, 38, 30)');
expect(css(c.getByText('Oczekuje').closest('app-badge')!).color).toBe('rgb(122, 79, 0)');
expect(css(c.getByText('Przetwarzanie').closest('app-badge')!).color).toBe('rgb(0, 82, 165)');
expect(done.querySelector('[aria-hidden="true"]')).not.toBeNull();
```

Progress: `<app-progress label="Przetwarzanie wniosek.pdf" />`.

```ts
const bar = c.getByRole('progressbar', { name: 'Przetwarzanie wniosek.pdf' });
expect(bar.hasAttribute('aria-valuenow')).toBe(false);
expect(css(bar).backgroundColor).toBe('rgb(234, 242, 251)');
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Badge: mapa status → `{ label, icon, classes }`: pending `… / bg-warning-subtle text-warning`, processing `⟳ / bg-primary-subtle text-primary`, done `✓ / bg-success-subtle text-success`, error `✕ / bg-danger-subtle text-danger`; host `inline-flex items-center gap-[5px] rounded-full px-[8px] py-px text-[12px] font-semibold`, klasy przez `computed()`. Progress: host `role="progressbar"`, `[attr.aria-label]="label()"`, `block h-[4px] overflow-hidden rounded-full bg-primary-subtle`; wewnętrzny pasek `bg-primary w-1/3` z animacją `translateX(-100%) → translateX(300%)` (keyframes w `styles` komponentu) i `motion-reduce:animate-none` / `@media (prefers-reduced-motion: reduce) { animation: none }`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(ui): add status badge and indeterminate progress`

### Task 3: `app-card` i `app-topbar`

**Files:**
- Create: `frontend/src/app/shared/ui/card/card.ts`, `card.stories.ts`
- Create: `frontend/src/app/shared/ui/topbar/topbar.ts`, `topbar.stories.ts`

**Interfaces:**
- Consumes: `Button` (Task 1) tylko w story karty.
- Produces: `Card` (`app-card`, sloty `<ng-content select="[cardTitle]" />`, `<ng-content select="[cardActions]" />`, `<ng-content />`; nagłówek renderowany zawsze); `Topbar` (`app-topbar`, `appName = input.required<string>()`, `userName = input.required<string>()`, `logout = output<void>()`, linki nawigacji przez `<ng-content />` wewnątrz `<nav aria-label="Główna">`).

- [ ] **Step 1: Write failing stories.** Card: `<app-card><h2 cardTitle>Kolejka</h2><button appButton cardActions variant="primary">Pobierz wszystkie (ZIP)</button><p>Treść</p></app-card>`.

```ts
const card = c.getByText('Treść').closest('app-card')!;
expect(css(card).backgroundColor).toBe('rgb(255, 255, 255)');
expect(css(card).borderRadius).toBe('6px');           // story PreviewTheme: '8px'
expect(c.getByRole('heading', { name: 'Kolejka' }).compareDocumentPosition(c.getByRole('button')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
```

Topbar (args `logout: fn()`): `<app-topbar appName="Cyfryzacja formularzy" userName="j.nowak" (logout)="logout()"><a href="#" aria-current="page">Import</a><a href="#">Walidator</a></app-topbar>`.

```ts
const header = c.getByRole('banner');
expect(css(header).backgroundColor).toBe('rgb(20, 35, 60)');
expect(within(c.getByRole('navigation', { name: 'Główna' })).getAllByRole('link')).toHaveLength(2);
expect(c.getByText('j.nowak')).toBeVisible();
await userEvent.click(c.getByRole('button', { name: 'Wyloguj' }));
expect(args.logout).toHaveBeenCalledOnce();
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Card: host `block bg-surface border border-border rounded-card`, nagłówek `flex items-center gap-[10px] px-[10px] py-[8px] border-b border-border`, akcje `ml-auto flex gap-[8px]`; projektowany tytuł stylowany `[&_[cardTitle]]:text-body [&_[cardTitle]]:font-semibold`. Topbar: `<header>` `bg-topbar text-on-topbar h-[44px] flex items-center gap-[20px] px-[16px]`, nazwa `font-bold`, linki `text-on-topbar opacity-75 hover:opacity-100 focus-ring`, `[aria-current=page]` → `opacity-100 border-b-2 border-on-topbar`; po prawej `userName` i natywny `<button type="button" class="focus-ring …">Wyloguj</button>` w kolorze `text-on-topbar` (nie `appButton` ghost, bo primary na granacie nie ma kontrastu).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(ui): add card and topbar`

### Task 4: `app-file-drop`

**Files:**
- Create: `frontend/src/app/shared/ui/file-drop/file-drop.ts`, `file-drop.stories.ts`

**Interfaces:**
- Consumes: `Button` (Task 1) dla „Wybierz pliki”.
- Produces: `FileDrop` (`app-file-drop`, `accept = input('.pdf,.doc,.docx,.ods,.xlsx,.jpg,.jpeg,.png')`, `maxSizeMb = input.required<number>()`, `filesSelected = output<File[]>()`). Host ma atrybut `data-dragging` gdy trwa przeciąganie.

- [ ] **Step 1: Write failing story** (args `filesSelected: fn()`, `maxSizeMb: 10`).

```ts
const input = canvasElement.querySelector('input[type=file]') as HTMLInputElement;
const a = new File(['a'], 'a.pdf', { type: 'application/pdf' });
const b = new File(['b'], 'b.docx');
// hint describes formats and limit
const btn = c.getByRole('button', { name: 'Wybierz pliki' });
expect(btn).toHaveAccessibleDescription('PDF, DOC, DOCX, ODS, XLSX, JPG, PNG · do 10 MB · wiele plików naraz');
expect(input.multiple).toBe(true);
expect(input.accept).toBe('.pdf,.doc,.docx,.ods,.xlsx,.jpg,.jpeg,.png');
// picking files emits them
await userEvent.upload(input, [a, b]);
expect(args.filesSelected).toHaveBeenLastCalledWith([a, b]);
// re-selecting the same file emits again
await userEvent.upload(input, [a]);
expect(args.filesSelected).toHaveBeenCalledTimes(2);
// drag state
const zone = canvasElement.querySelector('app-file-drop')!;
const dt = new DataTransfer(); dt.items.add(b);
fireEvent.dragOver(zone, { dataTransfer: dt });
expect(zone.hasAttribute('data-dragging')).toBe(true);
fireEvent.drop(zone, { dataTransfer: dt });
expect(zone.hasAttribute('data-dragging')).toBe(false);
expect(args.filesSelected).toHaveBeenLastCalledWith([b]);
// drop without files emits nothing
fireEvent.drop(zone, { dataTransfer: new DataTransfer() });
expect(args.filesSelected).toHaveBeenCalledTimes(3);
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Szablon: tekst „Przeciągnij pliki tutaj lub”, `<button appButton type="button" [attr.aria-describedby]="hintId" (click)="input.click()">Wybierz pliki</button>`, hint `<small [id]="hintId">PDF, DOC, DOCX, ODS, XLSX, JPG, PNG · do {{ maxSizeMb() }} MB · wiele plików naraz</small>`, `<input #input type="file" multiple class="sr-only" tabindex="-1" [accept]="accept()" (change)="…">`. Po emisji `input.value = ''`. Host: `(dragover)` → `preventDefault()` + `dragging.set(true)`, `(dragleave)` → `false`, `(drop)` → `preventDefault()`, `false`, emituj `Array.from(dt.files)` tylko gdy długość > 0. `hintId` unikalny per instancja (licznik modułowy). Styl: `block border-2 border-dashed border-border-input rounded-card bg-surface p-[18px] text-center text-fg-secondary`, `data-[dragging]:border-primary data-[dragging]:bg-primary-subtle`, hint `block text-fg-muted mt-[4px]`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(ui): add file drop zone`

### Task 5: Story „Kolejka (kompozycja)”

**Files:**
- Create: `frontend/src/app/shared/ui/queue-composition.stories.ts`

**Interfaces:**
- Consumes: `Card`, `Table`, `Badge`, `FileStatus`, `Button`, `Progress`, `FileDrop`, `Topbar` (Tasks 1–4). Nie tworzy nowych komponentów (harness tylko w pliku story).

- [ ] **Step 1: Write the story** odtwarzającą makietę A: topbar, nagłówek „Import formularzy” (`text-title font-semibold`), file-drop, card „Kolejka” z licznikiem „4 pliki · 1 gotowy · 1 błąd” i „Pobierz wszystkie (ZIP)”, tabela Plik / Rozmiar / Status / Akcje z wierszami: `Deklaracja o wysokości opłaty.docx` 84 KB done + „Otwórz wynik”; `Wniosek o dowód.pdf` 1,2 MB processing + progress; `Skan wniosku.jpg` 2,4 MB pending + „Usuń”; `formularz_z_bardzo_dluga_nazwa_bez_spacji_0123456789_0123456789_0123456789.jpe` 40 KB error, komunikat „Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.” (`text-danger text-[12px]`) + „Ponów”, „Usuń”. Komórka nazwy: `break-all`. Nazwy przycisków w wierszach unikalne dla czytnika: `aria-label="Usuń Skan wniosku.jpg"` itd.

```ts
expect(c.getAllByRole('row')).toHaveLength(5);
for (const t of ['Gotowe', 'Przetwarzanie', 'Oczekuje', 'Błąd']) expect(c.getByText(t)).toBeVisible();
// long file name does not overflow card
const card = c.getByRole('table').closest('app-card') as HTMLElement;
expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth);
```

- [ ] **Step 2: Run** `npm run test:storybook` → PASS (także a11y w obu motywach). Jeśli overflow: popraw klasę komórki, nie test.
- [ ] **Step 3: Commit** `test(ui): add import queue composition story`
