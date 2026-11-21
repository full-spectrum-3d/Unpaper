# Renderer — słowniki i combobox: plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pola `SELECT` ze słownikiem w podglądzie formularza działają jak na makietach COI: Kraj z „Polska” i wyszukiwaniem, TERYT jako kaskada województwo → powiat → gmina → miejscowość.

**Architecture:** Dane przykładowe słowników leżą w `features/preview/dictionaries.mock.ts`. Generyczny `app-combobox` (ARIA 1.2) w `shared/ui/combobox` zastępuje natywny `<select>` w polu SELECT. Słownik wielopoziomowy renderuje nowy komponent `app-dictionary-cascade-field`, który `field-host` wybiera na podstawie słownika. Jego odpowiedź w `AnswersStore` to `string[]`.

**Tech Stack:** Angular 22 (standalone, zoneless, sygnały), Tailwind 4 z tokenami, Vitest (jsdom), Storybook 10 + addon a11y.

**Spec:** `docs/superpowers/specs/2026-11-21-form-renderer-dictionaries-design.md`

## Global Constraints

- Bez nowych zależności npm.
- Angular: `input()/model()/output()`, `inject()`, natywny control flow, bez jawnego `ChangeDetectionStrategy` (domyślny OnPush w v22, konwencja projektu), bez `@HostListener` (`host: {}`).
- Wywołania funkcji nie mogą stać w wiązaniach dwukierunkowych. W polach używaj `[value]` + `(valueChange)`.
- Odpowiedź Kraju zostaje stringiem (zapytania jsonata: `"Polska" in …__userAnswer`).
- Copy (dokładnie): placeholder `Wybierz`, brak wyników `Brak wyników`, pusty słownik `Brak pozycji w słowniku <nazwa>`, przycisk ✕ `aria-label="Wyczyść: <etykieta>"`, poziomy TERYT `Województwo`, `Powiat`, `Gmina`, `Miejscowość`.
- Reguła wyszukiwania: `searchable = searchEnabled === true || liczbaOpcji > 20`.
- Niepuste `field.options` mają pierwszeństwo przed słownikiem.
- Testy: `cd frontend && source ~/.nvm/nvm.sh && nvm use >/dev/null && npx ng test --watch=false` oraz `npm run test:storybook` (a11y = `error`). Obie komendy w tym samym wywołaniu powłoki co `nvm use`.
- Commity w konwencji `typ(zakres): opis`, **bez** stopki `Co-Authored-By`.

## Review Focus

1. Kraj zmieniony z „Polska” na inny kraj, a potem z powrotem: ścieżka TERYT zostaje zachowana, ale niewidoczna. Pole jest ukryte, a nie usunięte ze store'u. Oczekiwane: po powrocie poprzedni wybór dalej widoczny. Bez testu, bo to zachowanie istniejącego store'u. Reviewer ma tylko sprawdzić, że kaskada niczego nie resetuje przy ukryciu.
2. Wpisanie tekstu bez wyboru i wyjście Tabem: wartość nie może zmienić się na wpisany tekst. Test w Task 2.
3. Filtrowanie „lodz” i „LÓDŹ” znajduje „Łódź”, a „slask” znajduje „śląskie”. Test w Task 2.
4. Dwa comboboxy na stronie (Kraj zamieszkania i Kraj siedziby): unikalne `id` inputów i listboxów, klik w jeden zamyka drugi. Test w Task 2.
5. Zmiana województwa po wybraniu całej ścieżki czyści powiat, gminę i miejscowość, a powiat pokazuje opcje nowego województwa. Test w Task 4.

---

### Task 1: Dane przykładowe słowników

**Files:**
- Create: `frontend/src/app/features/preview/dictionaries.mock.ts`
- Test: `frontend/src/app/features/preview/dictionaries.mock.spec.ts`

**Interfaces:**
- Produces:
  ```ts
  export interface DictionaryNode { name: string; children?: DictionaryNode[] }
  export interface Dictionary { levels: string[]; items: DictionaryNode[] }
  export const SAMPLE_DICTIONARIES: Readonly<Record<string, Dictionary>>;
  export function findDictionary(name: string | undefined): Dictionary | undefined;
  ```

- [ ] **Step 1: Write the failing test** `dictionaries.mock.spec.ts`:
  - `findDictionary('Kraje')` ma `levels` `['Kraj']`, zawiera `Polska`, `Niemcy`, `Ukraina`, ma ≥ 190 pozycji i jest posortowane `localeCompare(…, 'pl')`.
  - `findDictionary('TERYT_4G_DOWODOWY').levels` to `['Województwo','Powiat','Gmina','Miejscowość']`. `items` ma dokładnie 16 nazw: `dolnośląskie, kujawsko-pomorskie, lubelskie, lubuskie, łódzkie, małopolskie, mazowieckie, opolskie, podkarpackie, podlaskie, pomorskie, śląskie, świętokrzyskie, warmińsko-mazurskie, wielkopolskie, zachodniopomorskie`.
  - Każde województwo ma ścieżkę głębokości 4 (rekurencyjnie: istnieje węzeł na poziomie 3 bez `children`). Każdy węzeł na poziomach 0–2 ma niepuste `children`.
  - `mazowieckie` i `małopolskie` mają ≥ 2 powiaty.
  - `findDictionary('TERYT_DOWODOWY')` jest tym samym obiektem co `TERYT_4G_DOWODOWY` (`toBe`).
  - `findDictionary('NUMERY_KIERUNKOWE').items` zawiera `+48 Polska`, ma ≥ 8 pozycji, `levels` `['Numer kierunkowy']`.
  - `findDictionary('Nieznany')` oraz `findDictionary(undefined)` zwracają `undefined`.
- [ ] **Step 2:** Uruchom `npx ng test --watch=false`. Oczekiwane: FAIL (brak modułu).
- [ ] **Step 3: Implement** `dictionaries.mock.ts`. Prawdziwe nazwy jednostek. Dla każdego województwa miasto wojewódzkie jako powiat → gmina → miejscowość (np. `mazowieckie › Warszawa › Warszawa › Warszawa`). Dla mazowieckiego i małopolskiego dodaj po 1–2 powiaty ziemskie z gminą i 1–2 miejscowościami. Kraje to pełna lista polskich nazw państw (ok. 195). Komentarz na górze: dane przykładowe do podglądu, backend nie dostarcza pozycji słowników predefiniowanych.
- [ ] **Step 4:** Uruchom testy. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(preview): add sample dictionaries for preview`

---

### Task 2: Komponent combobox

**Files:**
- Create: `frontend/src/app/shared/ui/combobox/combobox.ts`, `frontend/src/app/shared/ui/combobox/matches.ts`
- Test: `frontend/src/app/shared/ui/combobox/combobox.spec.ts`, `frontend/src/app/shared/ui/combobox/matches.spec.ts`
- Create: `frontend/src/app/shared/ui/combobox/combobox.stories.ts` (title `UI/Combobox`)

**Interfaces:**
- Produces:
  ```ts
  // matches.ts
  export function foldText(s: string): string; // lower-case, bez diakrytyków, ł→l
  export function filterOptions(options: readonly string[], query: string): string[];
  // combobox.ts — selector 'app-combobox', class Combobox implements FormValueControl<string>
  value = model('');
  options = input.required<readonly string[]>();
  label = input.required<string>();
  labelHidden = input(false);
  searchable = input(false);
  placeholder = input('Wybierz');
  describedBy = input<string | null>(null);
  emptyText = input('Brak wyników');
  readonly inputId: string; // 'app-combobox-<n>' z licznika modułu, jak TextField
  // Slot <ng-content select="[description]"> renderowany między etykietą a inputem.
  ```

- [ ] **Step 1: Write failing tests** `matches.spec.ts`:
  - `foldText('Łódź')` → `'lodz'`, `foldText('ŚLĄSKIE')` → `'slaskie'`.
  - `filterOptions(['Łódź','Lublin','śląskie'], 'lodz')` → `['Łódź']`, z zapytaniem `'LÓDŹ'` → `['Łódź']`, z `'slask'` → `['śląskie']`. Pusty `query` zwraca wszystkie (ta sama kolejność). `'ub'` → `['Lublin']` (dopasowanie `includes`).
- [ ] **Step 2: Write failing tests** `combobox.spec.ts` (TestBed, `provideZonelessChangeDetection`, host z dwoma comboboxami: `options = ['Polska','Niemcy','Norwegia']`, `[(value)]` do sygnału):
  - input ma `role="combobox"`, `aria-expanded="false"`. `<label for>` wskazuje `inputId`. Bez wartości input pokazuje placeholder `Wybierz`.
  - `ArrowDown` otwiera listbox (`aria-expanded="true"`, `aria-controls` = id listboxa, 3× `role="option"`) i ustawia `aria-activedescendant` na pierwszą opcję. Drugi `ArrowDown` przesuwa na drugą. `End` → ostatnia, `Home` → pierwsza. `Enter` ustawia sygnał na aktywną opcję i zamyka listę.
  - `Escape` przy otwartej liście zamyka ją bez zmiany wartości.
  - `searchable=true`: wpisanie `'nor'` zostawia 1 opcję `Norwegia`. Wpisanie `'xyz'` pokazuje tekst `Brak wyników`. Wpisanie `'nor'` i `Tab` (blur) nie zmienia sygnału, a input wraca do poprzedniej wartości.
  - `searchable=false`: input ma `readonly` i nie ma `aria-autocomplete`.
  - Z wartością `Polska` widoczny jest przycisk `aria-label="Wyczyść: Kraj"`. Klik ustawia `''`, a fokus jest na inpucie. Bez wartości przycisku nie ma.
  - Opcja wybrana ma `aria-selected="true"`.
  - Dwa comboboxy mają różne `inputId` i id listboxów. Otwarcie drugiego (klik) przy otwartym pierwszym zamyka pierwszy (`pointerdown` poza hostem).
  - Klik w opcję wybiera ją.
  - Element z atrybutem `description` przekazany do slotu stoi w DOM między `<label>` a inputem.
- [ ] **Step 3:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 4: Implement** `matches.ts` (`normalize('NFD')`, usunięcie `\p{Diacritic}`, `ł`→`l`) i `Combobox`.
  - Stan wewnętrzny: `open = signal(false)`, `query = signal('')`, `active = signal(0)`, `visible = computed(() => searchable() ? filterOptions(options(), query()) : options())`.
  - Input pokazuje `open() && searchable() ? query() : value()`.
  - Zamknięcie listy zawsze czyści `query`.
  - `host: { '(document:pointerdown)': 'onDocPointer($event)' }` zamyka listę, gdy cel jest poza hostem.
  - Klasy inputu jak w `TextField` (`block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y focus-ring`) plus prawy padding na ✕ i chevron. Ikony to inline SVG z `aria-hidden="true"`. Chevron nie jest przyciskiem: klik w niego przekazuje fokus i otwiera.
  - Listbox jest `absolute` pod polem, `max-h-64 overflow-auto`, `bg-surface border border-border-input rounded-field`. Aktywna opcja ma tło tokenem hover/selected z `tokens.css` (użyj istniejącego, np. `bg-surface-hover`, jeśli jest; w przeciwnym razie `bg-bg`). Aktywna opcja jest przewijana do widoku (`scrollIntoView({block:'nearest'})`, z guardem dla jsdom: `?.`).
- [ ] **Step 5:** Uruchom testy. Oczekiwane: PASS.
- [ ] **Step 6: Stories** `UI/Combobox`: `Domyślny`, `ZWartością` (Polska), `Wyszukiwanie` (lista krajów z `findDictionary('Kraje')`, `searchable`), `PustaLista` (`emptyText="Brak pozycji w słowniku X"`). Play w `Wyszukiwanie`: wpisz `pol`, `Enter`, oczekuj wartości `Polska` w inpucie.
- [ ] **Step 7:** `npm run test:storybook`. Oczekiwane: PASS, brak naruszeń a11y.
- [ ] **Step 8: Commit** `feat(ui): add accessible combobox with search`

---

### Task 3: Pole SELECT na comboboxie

**Files:**
- Modify: `frontend/src/app/features/preview/form-definition.ts` (dodaj `searchEnabled?: boolean | null; multiLevelTree?: boolean;` do `FormField`)
- Create: `frontend/src/app/features/preview/select-options.ts`
- Test: `frontend/src/app/features/preview/select-options.spec.ts`
- Modify: `frontend/src/app/features/preview/fields/select.ts`

**Interfaces:**
- Consumes: `findDictionary`, `Dictionary` (Task 1); `Combobox` (Task 2).
- Produces:
  ```ts
  // select-options.ts
  export function isCascade(field: FormField): boolean; // brak niepustych options && findDictionary(field.dictionaryName)?.levels.length > 1
  export function selectOptions(field: FormField): string[]; // niepuste options → ich `name`; inaczej nazwy items słownika (poziom 0); inaczej []
  export function isSearchable(field: FormField, optionCount: number): boolean; // searchEnabled === true || optionCount > 20
  ```

- [ ] **Step 1: Write failing tests** `select-options.spec.ts`:
  - `selectOptions({…, options:[{id:'1',name:'A'}], dictionaryName:'Kraje'})` → `['A']`.
  - `selectOptions({…, dictionaryName:'Kraje'})` zawiera `'Polska'`. `selectOptions({…, dictionaryName:'Nieznany'})` → `[]`.
  - `isCascade` → `true` dla `TERYT_4G_DOWODOWY` i `TERYT_DOWODOWY` (także przy `multiLevelTree:false`), `false` dla `Kraje`, `false` dla TERYT z niepustymi `options`.
  - `isSearchable({searchEnabled:true}, 3)` → `true`, `isSearchable({searchEnabled:null}, 21)` → `true`, `isSearchable({}, 20)` → `false`.
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 3: Implement** `select-options.ts`. Pole `SelectField` renderuje opis (bez zmian) i `app-combobox` z:
  - `[label]="label()"`, `[labelHidden]="!hasTitle()"`, `[options]`, `[searchable]`, `[describedBy]="describedBy()"`, `[value]="value() ?? ''"`, `(valueChange)="set($event)"`,
  - `emptyText`: przy pustych opcjach i ustawionym `dictionaryName` → `Brak pozycji w słowniku <dictionaryName>`, inaczej domyślny.
  - Opis pola trafia do slotu `description` comboboxa (element z atrybutem `description`), żeby stał między etykietą a inputem.
- [ ] **Step 4:** Uruchom testy i zaktualizuj istniejące testy/story pola SELECT, które szukały `<select>` / `option` „Słownik: …” (`grep -rn "Słownik:" frontend/src`). Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(preview): render select fields with combobox and dictionaries`

---

### Task 4: Kaskada TERYT

**Files:**
- Create: `frontend/src/app/features/preview/fields/dictionary-cascade.ts`
- Test: `frontend/src/app/features/preview/fields/dictionary-cascade.spec.ts`
- Modify: `frontend/src/app/features/preview/answers-store.ts` (`initialAnswer`), `answers-store.spec.ts`
- Modify: `frontend/src/app/features/preview/field-host.ts`
- Modify: `frontend/src/app/features/preview/fields.stories.ts` (pole `TERYT_4G_DOWODOWY`), `form-renderer.spec.ts`

**Interfaces:**
- Consumes: `isCascade`, `isSearchable` (Task 3); `findDictionary`, `DictionaryNode` (Task 1); `Combobox` (Task 2); `FieldBase<T>`.
- Produces: `DictionaryCascadeField extends FieldBase<string[]>`, selector `app-dictionary-cascade-field`. Eksportowana czysta funkcja `cascadeLevels(dict: Dictionary, path: readonly string[]): { label: string; options: string[] }[]`, która zwraca poziomy do wyrenderowania.

- [ ] **Step 1: Write failing tests**
  - `answers-store.spec.ts`: `initialAnswer({type:'SELECT', dictionaryName:'TERYT_4G_DOWODOWY', defaultValue:[]})` → `[]`, z `defaultValue:['mazowieckie']` → `['mazowieckie']`. Kraj bez zmian (`'Polska'`).
  - `dictionary-cascade.spec.ts`:
    - `cascadeLevels(teryt, [])` → 1 poziom `{label:'Województwo'}` z 16 opcjami.
    - `cascadeLevels(teryt, ['mazowieckie'])` → 2 poziomy, drugi `Powiat` z ≥ 2 opcjami zawierającymi `'Warszawa'`.
    - Pełna ścieżka do miejscowości daje 4 poziomy. Ścieżka z nieistniejącą nazwą (`['Atlantyda']`) daje 1 poziom.
    - Komponent (TestBed z `AnswersStore` w providers): wybór `mazowieckie` w pierwszym comboboxie pokazuje etykietę `Powiat`. Wybór pełnej ścieżki, potem zmiana województwa na `małopolskie` → odpowiedź `['małopolskie']`, widoczne 2 comboboxy, opcje powiatu z małopolskiego.
    - Przy `title === dictionaryName` nie ma widocznego tekstu `TERYT_4G_DOWODOWY`. Przy `title: 'Adres w Polsce'` jest nagłówek z tym tekstem, a grupa ma `aria-labelledby`.
  - `form-renderer.spec.ts`: na mocku `nadplata-podatku.json` krok z adresem pokazuje combobox `Kraj` z wartością `Polska` i combobox `Województwo`. Klik w `Wyczyść: Kraj` → po ewaluacji widoczności nie ma `Województwo` (ten sam sposób oczekiwania na widoczność co istniejące testy SHOW/HIDE).
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 3: Implement**
  - `initialAnswer`: gałąź `isCascade(field)` przed gałęzią SELECT zwraca `[defaultValue].flat().filter(Boolean)`.
  - `DictionaryCascadeField`: `div role="group"`, comboboxy z `cascadeLevels(dict, value())`. `(valueChange)` poziomu `i` ustawia `[...value().slice(0, i), v].filter(Boolean)`, czyli pusta wartość ✕ obcina od poziomu i. Odstęp między comboboxami `space-y-4` (jak odstęp wierszy siatki; sprawdź `renderer-grid.ts`). `searchable` na poziomie = `isSearchable(field, options.length)`. Opis pola (jeśli jest) pod nagłówkiem, `describedBy` tylko dla pierwszego comboboxa.
  - `field-host`: w `@case ('SELECT')` → `@if (isCascade(field())) { cascade } @else { select }`.
- [ ] **Step 4:** Uruchom `npx ng test --watch=false`. Oczekiwane: PASS.
- [ ] **Step 5:** Story `Podgląd/Pola`: dodaj pole TERYT (`dictionaryName:'TERYT_4G_DOWODOWY', title:'TERYT_4G_DOWODOWY', searchEnabled:true`) i dla pola Kraj `defaultValue:['Polska'], searchEnabled:true`. `npm run test:storybook`. Oczekiwane: PASS, brak naruszeń a11y.
- [ ] **Step 6: Commit** `feat(preview): render TERYT dictionaries as cascading comboboxes`
