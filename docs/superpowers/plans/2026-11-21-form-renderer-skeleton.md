# Renderer formularza – szkielet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Klikalny podgląd formularza e-usługi z JSON-a COI na ekranie wyniku: strony wg `flow`, sekcje i wszystkie typy pól w siatce, lokalne odpowiedzi i warunki widoczności SHOW/HIDE przez `jsonata`.

**Architecture:** Czyste funkcje (`orderTabs`, `isFormDefinition`, `withUserAnswers`, `evaluateVisibility`) + `AnswersStore` (provider komponentu renderera, `Map<fieldId, WritableSignal>` i sygnał wersji) + drzewo komponentów `FormRenderer` → `RendererGrid` (rekurencyjnie) → `FieldHost` → komponent na typ pola. Renderer osadzony w `ResultPage` w kontenerze `data-theme="preview"`.

**Tech Stack:** Angular 22 (standalone, signals, zoneless), Tailwind 4 (motyw `preview`), `jsonata@^2.2.2` (MIT, w leniwym chunku strony wyniku), Vitest (`ng test`), Storybook 10.

**Spec:** `docs/superpowers/specs/2026-11-21-form-renderer-skeleton-design.md` (sekcje „Rozstrzygnięcia” i „Decyzja użytkownika po przeglądzie” wiążą).

## Global Constraints

- Wzorcowe JSON-y: `frontend/src/app/features/import/mock-forms/nadplata-podatku.json` i `numer-porzadkowy.json` (testy i stories importują je stamtąd).
- Wartości odpowiedzi: RADIO/SELECT → `string` (nazwa opcji; `defaultValue`-tablica → pierwszy element); CHECKBOX → `string[]`; CONSENT_SECTION → `boolean[]`; FILE_UPLOADER → `string[]` nazw; DATEPICKER → `YYYY-MM-DD`; reszta → `string`.
- `EXTERNAL_SYSTEM`: `defaultValue` to ścieżka; wartość z `SAMPLE_REGISTRY_DATA` (nieznana ścieżka → `''`).
- Widoczność: widoczne ⇔ (brak SHOW ∨ ∃ SHOW truthy) ∧ ¬∃ HIDE truthy; błąd zapytania → widoczne + `console.warn`; ukryta sekcja ukrywa zawartość; ukryte odpowiedzi zachowane; do pierwszego wyniku pola z SHOW ukryte.
- Nagłówki w renderze: tytuł formularza `h2`, „Krok N z M: <tytuł strony>” `h3` (`tabindex="-1"`, cel fokusu), na `FINISH` „Podsumowanie”; tytuły sekcji `h4`.
- Teksty: „Przerwij wypełnianie”, „Wstecz”, „Dalej”, „Wybierz”, „Słownik: <nazwa>”, „Dodaj lub przeciągnij plik”, „Dopuszczalny format pliku”, „Maksymalny rozmiar pliku”, „Maksymalna liczba plików”, „Nieobsługiwany typ pola: <type>”, „Podgląd formularza”, „JSON”, „Nie można wyświetlić podglądu: wynik nie ma struktury formularza.”; licznik textarea „N/8000”.
- Siatka: `grid grid-cols-3`, `grid-auto-rows: auto`, `grid-area: {y+1} / {x+1} / span {rows} / span {cols}`; kolejność DOM wg `y`, potem `x`; poniżej `sm` jedna kolumna.
- Opisy HTML przez `[innerHTML]` (sanitizer Angulara); pusty szkielet `<html><head></head><body></body></html>` = brak opisu.
- Angular: standalone, `inject()`, signals, bez jawnego `OnPush`, semantyczne klasy Tailwind, `focus-ring`, WCAG 2.1 AA (`fieldset`/`legend` dla grup), teksty po polsku.
- Node: `cd frontend && source ~/.nvm/nvm.sh && nvm use` w tym samym wywołaniu powłoki co `ng`/`npm`. Testy: `npx ng test --watch=false`, `npm run test:storybook`, `npx ng build` – zielone na końcu każdego zadania.
- Jedyna nowa zależność: `jsonata@^2.2.2`. Commity w Conventional Commits, bez `Co-Authored-By`.

## Review Focus

1. **Wynik nie będący formularzem** (np. `{}`, tablica, `null`, tekst) – komunikat zamiast wyjątku → test `rejects non-form results` (Task 1) i story `NotAForm` (Task 5).
2. **`flow.links` z cyklem lub wskazujące nieistniejącą stronę** – każda strona raz, bez zawieszenia → test `breaks cycles` i `ignores dangling links` (Task 1).
3. **Pole bez `title`/`options`/`repeatingSectionGrid`** (brakujące klucze z LLM) – renderuje się bez błędu → story `SparseFields` (Task 3).
4. **Zapytanie `jsonata` z błędem składni lub odwołaniem do nieistniejącej strony** – pole widoczne, reszta działa → test `fail-open on broken query` (Task 2).
5. **Szybkie klikanie radia** (kilka zmian przed końcem ewaluacji) – wynik odpowiada ostatniej odpowiedzi, nie wcześniejszej → test `latest answers win` (Task 4).

---

### Task 1: Model, kolejność stron, odpowiedzi i dane z rejestru

**Files:**
- Create: `frontend/src/app/features/preview/form-definition.ts`, `form-definition.spec.ts`, `page-order.ts`, `page-order.spec.ts`, `answers-store.ts`, `answers-store.spec.ts`, `with-user-answers.ts`, `with-user-answers.spec.ts`, `sample-registry-data.ts`, `html-text.ts`, `html-text.spec.ts`
- Delete: `frontend/src/app/features/preview/.gitkeep`

**Interfaces:**
- Produces: typy `FormDefinition`, `FormTab`, `Question`, `FormField`, `FieldOption`, `FieldState`, `ConsentSectionConfig`, `FlowLink` (wg spec „Model”; `FormField.type: string`), `KNOWN_FIELD_TYPES`; `isFormDefinition(value: unknown): value is FormDefinition`; `orderTabs(def: FormDefinition): FormTab[]`; `sortQuestions(qs: Question[]): Question[]` (wg `y`, potem `x`); `hasText(html: string | undefined): boolean`; `SAMPLE_REGISTRY_DATA: Readonly<Record<string, string>>`; `initialAnswer(field: FormField): unknown`; `AnswersStore` (`@Injectable()` – provider komponentu): `answer(field: FormField): WritableSignal<unknown>`, `version: Signal<number>` (rośnie przy każdej zmianie dowolnej odpowiedzi), `reset(): void`, `snapshot(): ReadonlyMap<string, unknown>`; `withUserAnswers(def: FormDefinition, answers: ReadonlyMap<string, unknown>): FormDefinition`.

- [ ] **Step 1: Write failing specs** – `form-definition.spec.ts`: `accepts reference forms` (oba wzorce → true), `rejects non-form results` (`null`, `{}`, `[]`, `'x'`, `{title:'a', tabs:{}}`, `{title:'a', tabs:[{}]}` → false). `page-order.spec.ts`: `orders by flow links` (wzorzec „nadpłata” → tytuły `['Dane','Informacje o nadpłacie','Kontakt i zgody','Strona końcowa']`), `starts at tab without incoming link` (tablica w odwrotnej kolejności → ten sam wynik), `no links keeps array order with FINISH last`, `breaks cycles` (A→B→A → `[A,B]`), `ignores dangling links`, `appends unreachable tabs`; `sortQuestions` wg y/x. `html-text.spec.ts`: pusty szkielet → false, `<p>tekst</p>` → true, `''`/`undefined` → false. `answers-store.spec.ts`: początkowe wartości (`TEXT_FIELD` z `defaultValue:'Urząd Gminy Ulan-Majorat'` → ta wartość; `SELECT` z `['Polska']` → `'Polska'`; `CHECKBOX` → `[]`; `CONSENT_SECTION` z 2 zgodami → `[false,false]`; `EXTERNAL_SYSTEM` `PESEL.name` → wartość z `SAMPLE_REGISTRY_DATA`; nieznana ścieżka → `''`), `version increments on set`, `reset restores initial values`, `answer returns same signal for same field`. `with-user-answers.spec.ts`: `inserts __userAnswer` (także w `repeatingSectionGrid`), `does not mutate input` (`structuredClone` porównanie), pola bez odpowiedzi nie mają klucza `__userAnswer`.
- [ ] **Step 2: Run** `npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement.** `orderTabs` wg spec („Kolejność stron”). `SAMPLE_REGISTRY_DATA`: przynajmniej `PESEL.name: 'JAN'`, `PESEL.surname: 'KOWALSKI'`, `PESEL.pesel: '51051101608'` + ścieżki `MLPZ.*` występujące we wzorcach (wyszukaj `EXTERNAL_SYSTEM` w obu plikach mock-forms i daj każdej ścieżce sensowną wartość testową). `AnswersStore.answer` tworzy sygnał leniwie z `initialAnswer`, a zmiany zwiększają `version` (np. owinięcie `set`/`update` albo `effect` – bez wycieków).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(preview): add form definition model, page order and answers store`

### Task 2: Widoczność SHOW/HIDE (`jsonata`)

**Files:**
- Create: `frontend/src/app/features/preview/visibility.ts`, `visibility.spec.ts`
- Modify: `frontend/package.json`, `package-lock.json` (`npm install jsonata@^2.2.2`)

**Interfaces:**
- Consumes: `FormDefinition`, `withUserAnswers` (Task 1).
- Produces: `evaluateVisibility(def: FormDefinition, answers: ReadonlyMap<string, unknown>): Promise<ReadonlySet<string>>` (zbiór `field.id` UKRYTYCH pól; ukrycie sekcji obejmuje jej potomków).

- [ ] **Step 1: Write failing specs** (na wzorcu „nadpłata”; pomocnik znajdujący `field.id` po `techName`): `default shows only base sections` – ukryte: „Dane podmiotu”, „Adres siedziby”, „Potwierdzenie, że jesteś reprezentantem”, „Dane innej osoby”, „Adres zamieszkania innej osoby”, „Pełnomocnictwo”, „Opłata skarbowa”, „Opłata skarbowa za pełnomonictwo” oraz radio `wybierz_jako_kto_wnioskujesz`; widoczne: „Urząd…”, „Podmiot wniosku”, „Twoje dane”, „Adres zamieszkania”. `other person shows its sections` – odpowiedź `wybierz_w_czyim_imieniu_wnioskujesz = 'Innej osoby'` → widoczne „Dane innej osoby”, „Adres zamieszkania innej osoby”, „Pełnomocnictwo”, „Opłata skarbowa”; „Dane podmiotu” nadal ukryte. `hidden section hides children` (dzieci ukrytej sekcji w zbiorze). `HIDE true hides` (syntetyczna definicja). `fail-open on broken query` (zapytanie `'('` → pole widoczne, `console.warn` wywołany z `techName`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`import jsonata from 'jsonata'`; cache skompilowanych wyrażeń po tekście; `await expr.evaluate(input)`; truthy = `true` albo tablica zawierająca `true`; pętla po wszystkich polach rekurencyjnie, ewaluacje równolegle przez `Promise.all`).
- [ ] **Step 4: Run** → PASS; `npm view jsonata license` → MIT.
- [ ] **Step 5: Commit** `feat(preview): evaluate SHOW/HIDE field states with jsonata`

### Task 3: Komponenty pól, `FieldHost` i `RendererGrid`

**Files:**
- Create: `frontend/src/app/features/preview/fields/*.ts` (section, text, textarea, radio, select, checkbox, date, file-uploader, text-block, consent-section, unknown), `field-host.ts`, `renderer-grid.ts`, `fields.stories.ts`
- Modify: `frontend/src/app/shared/ui/text-field/text-field.ts` (+ story) – wejście `readonly = input(false)`: atrybut `readonly` na `<input>` i tło `bg-surface-readonly`

**Interfaces:**
- Consumes: Task 1 (`FormField`, `Question`, `AnswersStore`, `hasText`, `sortQuestions`).
- Produces: `FieldHost` (`app-field-host`, `field = input.required<FormField>()`, `hidden = input<ReadonlySet<string>>(new Set())`); `RendererGrid` (`app-renderer-grid`, `questions = input.required<Question[]>()`, `hidden` jak wyżej) – pomija pytania, których `field.id` jest w `hidden`; komponenty pól czytają odpowiedź przez `inject(AnswersStore).answer(field)`.

- [ ] **Step 1: Write failing stories** (`Podgląd/Pola`, dekorator z `providers: [AnswersStore]` i `globals: { theme: 'preview' }`): story `AllTypes` – siatka z jednym polem każdego typu: TEXT_FIELD readOnly z wartością „Urząd Gminy Ulan-Majorat” (`toHaveAttribute('readonly')`), NUMBER (`inputmode="decimal"`), TEXTAREA (wpisanie „abc” → licznik „3/8000”), RADIO (`getByRole('group', {name})` zawiera 3 radia; klik → zaznaczone), SELECT z opcjami (pierwsza opcja „Wybierz”), SELECT ze słownikiem bez opcji (opcja „Słownik: Kraje” `disabled`), CHECKBOX, DATEPICKER (`type="date"`), FILE_UPLOADER (przycisk „Dodaj lub przeciągnij plik”, upload pliku `a.pdf` → nazwa widoczna; tabelka z „10 MB”), TEXT_BLOCK z HTML `<p>Ważne</p><script>x</script>` (tekst „Ważne” widoczny, brak `<script>`), CONSENT_SECTION (grupa z checkboxem, etykieta z HTML zgody), nieznany typ `FOO` („Nieobsługiwany typ pola: FOO”); story `SectionNested` – SECTION z `h4` i zagnieżdżonymi polami w siatce, `grid-area` elementu = `1 / 1 / span 1 / span 3`; story `HiddenField` – `hidden` z id pola → pole nieobecne; story `SparseFields` – pola bez `title`, `options`, `repeatingSectionGrid` renderują się bez wyjątku. a11y w motywie `preview`. Story `text-field` `ReadOnly`.
- [ ] **Step 2: Run** `npm run test:storybook` → FAIL.
- [ ] **Step 3: Implement** wg spec („Pola”); wspólna etykieta/opis przez `hasText`; `RendererGrid` używa `sortQuestions` i `[style.grid-area]`; rekurencja: `SectionField` używa `RendererGrid` (`forwardRef`/importy standalone).
- [ ] **Step 4: Run** wszystkie testy i build → PASS.
- [ ] **Step 5: Commit** `feat(preview): add field components and recursive grid`

### Task 4: `FormRenderer` – strony, nawigacja, widoczność

**Files:**
- Create: `frontend/src/app/features/preview/form-renderer.ts` (+ `.html`), `form-renderer.stories.ts`, `form-renderer.spec.ts`

**Interfaces:**
- Consumes: Task 1–3 (`orderTabs`, `AnswersStore`, `evaluateVisibility`, `RendererGrid`).
- Produces: `FormRenderer` (`app-form-renderer`, `definition = input.required<FormDefinition>()`, `providers: [AnswersStore]`).

- [ ] **Step 1: Write failing tests** – `form-renderer.spec.ts` (TestBed, wzorzec „nadpłata”): `latest answers win` (ustaw radio „Innej osoby”, potem natychmiast „Swoim”, `await` aż ewaluacja się zakończy → „Dane innej osoby” niewidoczne). Stories `Ekrany/Podgląd formularza` (motyw `preview`): `Nadplata` – `h2` „Wniosek o stwierdzenie nadpłaty podatku”, `h3` „Krok 1 z 3: Dane”, pole tylko do odczytu „Urząd Gminy Ulan-Majorat”, brak sekcji „Dane innej osoby”, brak przycisku „Wstecz”; klik „Innej osoby” → sekcja „Dane innej osoby” pojawia się (`findByRole('heading', { name: 'Dane innej osoby' })`); wpisanie wartości w pole tekstowe na kroku 1, „Dalej” → „Krok 2 z 3: Informacje o nadpłacie” i `document.activeElement` = ten `h3`; „Wstecz” → wartość zachowana; „Przerwij wypełnianie” → wartość pusta, krok 1; przejście do końca → `h3` „Podsumowanie”, brak „Dalej”. `NumerPorzadkowy` – renderuje `h2` tytułu drugiego wzorca i „Krok 1 z 3”. a11y.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `pages = computed(() => orderTabs(definition()))`, `index = signal(0)`; `hidden = signal<ReadonlySet<string> | null>(null)` (null = jeszcze nie policzone → `RendererGrid` dostaje zbiór wszystkich pól z SHOW); efekt: przy zmianie `store.version()`/`definition()` uruchom `evaluateVisibility` po mikrozadaniu z licznikiem żądań (wynik starszego żądania ignorowany). Fokus na `h3` przez `afterNextRender` po zmianie `index`, `window.scrollTo({ top: 0 })`. Układ przycisków jak na zrzutach (`justify-between`; „Przerwij wypełnianie” jako `button` w stylu linku).
- [ ] **Step 4: Run** wszystkie testy i build → PASS.
- [ ] **Step 5: Commit** `feat(preview): add form renderer with page navigation and visibility`

### Task 5: Podgląd na ekranie wyniku

**Files:**
- Modify: `frontend/src/app/features/result/result-page.ts` (+ `.html`), `result-page.stories.ts`

**Interfaces:**
- Consumes: `FormRenderer`, `isFormDefinition` (Task 1, 4).
- Produces: przełącznik „Podgląd formularza / JSON” na `/result/:id`.

- [ ] **Step 1: Write failing stories** – `Done` (wynik = wzorzec „nadpłata”): domyślnie widoczny `h2` tytułu formularza w kontenerze z `data-theme="preview"`, przełącznik z dwoma przyciskami (`aria-pressed="true"` na „Podgląd formularza” albo `role="tab"` `aria-selected`), klik „JSON” → `<pre>` z JSON-em, „Pobierz .json” nadal jest; `NotAForm` (wynik `{ foo: 1 }`) → komunikat „Nie można wyświetlić podglądu: wynik nie ma struktury formularza.” i od razu widoczny `<pre>`; `Unavailable` bez zmian. a11y.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** – renderer poza istniejącą kartą/nagłówkiem strony, na pełną szerokość, `<div data-theme="preview" class="bg-bg …">`.
- [ ] **Step 4: Run** wszystkie testy i `npx ng build` → PASS; zanotuj rozmiar initial bundle i nazwę chunka z `jsonata` (musi być leniwy).
- [ ] **Step 5: Commit** `feat(result): show form preview with JSON toggle`
