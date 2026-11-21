# Renderer — walidacja, READ_ONLY, podpowiedzi, dane z rejestru: plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Podgląd formularza waliduje pola przy „Dalej” (fokus na pierwszym błędzie, potem na bieżąco), blokuje pola stanem `READ_ONLY`, pokazuje `tooltipMessage` i oznacza dane z rejestru. Mocki dostają walidatory jak z backendu.

**Architecture:** Czyste funkcje (`validators.ts`, `validate-step.ts`) liczą błędy. `evaluateStates` zastępuje `evaluateVisibility` i zwraca `hidden` + `readOnly`. Serwis komponentu `FormState` (obok `AnswersStore` w `FormRenderer.providers`) trzyma `readOnly` i widoczne `errors`, a pola czytają go przez `FieldBase`. Wspólny `app-field-tooltip` w `shared/ui` obsługuje podpowiedzi.

**Tech Stack:** Angular 22 (zoneless, sygnały), jsonata, Tailwind 4 z tokenami, Vitest (jsdom), Storybook 10 + a11y.

**Spec:** `docs/superpowers/specs/2026-11-21-form-renderer-validation-design.md` (z sekcją „Doprecyzowania”).

## Global Constraints

- Bez nowych zależności npm.
- Angular: `input()/model()`, `inject()`, natywny control flow, `host: {}` zamiast `@HostListener`, bez jawnego `ChangeDetectionStrategy`. Bez wywołań funkcji w wiązaniach dwukierunkowych (`[value]` + `(valueChange)`).
- Kody walidatorów: `REQUIRED, EMAIL, PESEL, NIP, REGON, ZIP_CODE, EPUAP, ADE, SERIAL_NUMBER_ID_CARD`. Nieznany kod jest ignorowany z jednym `console.warn` na kod.
- Komunikaty (dokładnie, bez kropki na końcu):
  - REQUIRED tekst/liczba/textarea/data: `Uzupełnij to pole`; SELECT/RADIO/kaskada: `Wybierz jedną z opcji`; CHECKBOX: `Zaznacz to pole`; CONSENT_SECTION: `Zaznacz wymaganą zgodę`; FILE_UPLOADER: `Dodaj plik`
  - PESEL `Wpisz poprawny numer PESEL: 11 cyfr`, NIP `Wpisz poprawny NIP: 10 cyfr`, REGON `Wpisz poprawny REGON: 9 lub 14 cyfr`, ZIP_CODE `Wpisz kod w formacie 00-000`, EMAIL `Wpisz adres e-mail, np. jan@domena.pl`, EPUAP `Wpisz adres skrytki ePUAP, np. /urzad/SkrytkaESP`, ADE `Wpisz adres do e-Doręczeń, np. AE:PL-12345-67890-ABCDE-12`, SERIAL_NUMBER_ID_CARD `Wpisz serię i numer dowodu: 3 litery i 6 cyfr`
- Inne copy: `dane z rejestru`; przycisk podpowiedzi `aria-label="Więcej informacji: <etykieta>"`.
- Wygląd błędu jak `app-text-field`: `border-danger`, pod polem `<span aria-hidden="true">✕</span> <komunikat>` w `text-danger`, `aria-invalid="true"`, komunikat w `aria-describedby`.
- Pola ukryte i tylko do odczytu (statyczne `readOnly` lub stan `READ_ONLY`) nie są walidowane.
- Testy: `cd frontend && source ~/.nvm/nvm.sh && nvm use >/dev/null && npx ng test --watch=false` i `npm run test:storybook` (a11y = error), każde w jednym wywołaniu powłoki.
- Commity `typ(zakres): opis`, **bez** `Co-Authored-By`.

## Review Focus

1. Wklejony NIP z myślnikami `123-456-32-18` albo PESEL ze spacjami → poprawny. Test w Task 1.
2. Pole wymagane pojawia się (SHOW) po zmianie odpowiedzi, gdy błędy są już pokazane → od razu pokazuje błąd. Pole, które zostało ukryte → jego błąd znika i nie blokuje. Test w Task 3.
3. „Dalej” kliknięte, zanim skończy się pierwsza ewaluacja stanów → używa `initiallyHidden`; pola SHOW nie blokują. Test w Task 3.
4. Pole w zamkniętym (ukrytym) rodzicu-sekcji z REQUIRED → nie blokuje. Test w Task 3 (`validateStep`).
5. Prefill z rejestru (`00-001`, `jan.kowalski@example.com`) nie blokuje „Dalej”. Test w Task 6.

---

### Task 1: Walidatory

**Files:**
- Create: `frontend/src/app/features/preview/validators.ts`
- Test: `frontend/src/app/features/preview/validators.spec.ts`

**Interfaces:**
- Consumes: `FormField` (`form-definition.ts`), `isCascade` (`select-options.ts`), `findDictionary` / `DictionaryNode` (`dictionaries.mock.ts`).
- Produces:
  ```ts
  export function validateField(field: FormField, answer: unknown): string | null;
  export function isEmptyAnswer(field: FormField, answer: unknown): boolean;
  ```

- [ ] **Step 1: Write failing tests** (helper `f(type, validation, extra?)`):
  - Poprawne (→ `null`): PESEL `44051401458`, `440 514 014 58`; NIP `1234563218`, `123-456-32-18`; REGON `123456785`, `12345678901235`; ZIP `00-001`; EMAIL `jan@domena.pl`; EPUAP `/urzad/SkrytkaESP`; ADE `AE:PL-12345-67890-ABCDE-12` i ta sama wartość małymi literami; dowód `ABA300000`, `aba300000`.
  - Błędne (→ komunikat z Global Constraints): PESEL `44051401459`, `4405140145`; NIP `1234563219`; REGON `123456784`, `12345678901234`, `1234567890`; ZIP `00001`; EMAIL `jan@domena`; EPUAP `urzad/Skrytka`; ADE `AE:PL-1234-67890-ABCDE-12`; dowód `ABA300001`, `AB1300000`.
  - Format na pustym polu bez REQUIRED → `null`. `['REQUIRED','PESEL']` na `''` → `Uzupełnij to pole`.
  - REQUIRED według typu: TEXT_FIELD `'  '` → `Uzupełnij to pole`; NUMBER `'0'` → `null`; SELECT `''` → `Wybierz jedną z opcji`; RADIO `''` → to samo; CHECKBOX `[]` → `Zaznacz to pole`; FILE_UPLOADER `[]` → `Dodaj plik`; DATEPICKER `''` → `Uzupełnij to pole`.
  - CONSENT_SECTION (`consentSectionConfig.consents` = `[{required:true},{required:false}]`): `[false,true]` → `Zaznacz wymaganą zgodę`, `[true,false]` → `null`, nawet bez `REQUIRED` w `validation`.
  - Kaskada (SELECT `dictionaryName:'TERYT_4G_DOWODOWY'`, `REQUIRED`): `[]` i `['mazowieckie']` → `Wybierz jedną z opcji`; pełna ścieżka do liścia (weź z `findDictionary`) → `null`.
  - Nieznany kod `['FOO']` → `null` i `console.warn` wywołane raz przy dwóch walidacjach (spy).
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL (brak modułu).
- [ ] **Step 3: Implement** według spec „Walidatory” (wagi, regexy, normalizacja: `trim`; dla PESEL/NIP/REGON usuń `[\s-]`). Dowód: wartości liter A=10…Z=35, wagi `7,3,1,9,7,3,1,7,3`, poprawny gdy suma ważona wszystkich 9 znaków `% 10 === 0`.
- [ ] **Step 4:** Uruchom testy. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(preview): add COI field validators`

---

### Task 2: Stany SHOW/HIDE/READ_ONLY

**Files:**
- Modify: `frontend/src/app/features/preview/visibility.ts`, `visibility.spec.ts`
- Modify: `frontend/src/app/features/preview/form-renderer.ts`, `form-renderer.spec.ts` (token i testy wyścigu)

**Interfaces:**
- Produces:
  ```ts
  export interface FieldStates { hidden: ReadonlySet<string>; readOnly: ReadonlySet<string> }
  export async function evaluateStates(def: FormDefinition, answers: ReadonlyMap<string, unknown>): Promise<FieldStates>;
  export const STATES_EVALUATOR: InjectionToken<typeof evaluateStates>; // zastępuje VISIBILITY_EVALUATOR, w form-renderer.ts
  ```
  `FormRenderer` ma `protected readonly hidden` (jak dziś) i nowy `readonly readOnlyIds: Signal<ReadonlySet<string>>` (pusty do pierwszej ewaluacji).

- [ ] **Step 1: Write failing tests** w `visibility.spec.ts` (na `evaluateStates`):
  - Pole ze stanem `READ_ONLY` z zapytaniem prawdziwym → jego id w `readOnly`; fałszywym → brak; zapytanie niekompilujące się → brak (fail-open) + `console.warn`.
  - Pole ukryte nie trafia do `readOnly`, nawet z prawdziwym `READ_ONLY`.
  - Istniejące testy widoczności przepisane na `(await evaluateStates(...)).hidden` przechodzą bez zmiany oczekiwań.
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.** `evaluateVisibility` usuń (jedyny konsument to renderer). Renderer: token `STATES_EVALUATOR`, `evaluated` przechowuje `FieldStates | null` (`equal` porównuje oba zbiory dotychczasowym `sameSet`), `hidden = evaluated()?.hidden ?? initiallyHidden()`, `readOnlyIds = evaluated()?.readOnly ?? EMPTY`. Fail-open w catch: `{ hidden: new Set(), readOnly: new Set() }`.
- [ ] **Step 4:** Dostosuj `form-renderer.spec.ts` (provider tokenu, evaluator zwraca `FieldStates`). Uruchom wszystkie testy. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(preview): evaluate READ_ONLY states alongside visibility`

---

### Task 3: Walidacja kroku, FormState i „Dalej”

**Files:**
- Create: `frontend/src/app/features/preview/validate-step.ts`, `validate-step.spec.ts`
- Create: `frontend/src/app/features/preview/form-state.ts`
- Modify: `frontend/src/app/features/preview/form-renderer.ts`, `form-renderer.html`, `form-renderer.spec.ts`
- Modify: `frontend/src/app/features/preview/field-host.ts` (`host: { class: 'block', '[attr.data-field-id]': 'field().id' }`)

**Interfaces:**
- Consumes: `validateField` (Task 1); `FieldStates`, `readOnlyIds` (Task 2); `AnswersStore.snapshot()`, `AnswersStore.version`.
- Produces:
  ```ts
  // validate-step.ts
  export function validateStep(questions: Question[], answers: ReadonlyMap<string, unknown>,
    hidden: ReadonlySet<string>, readOnly: ReadonlySet<string>): Map<string, string>;
  // form-state.ts — @Injectable(), w FormRenderer.providers
  export class FormState {
    readonly readOnly: WritableSignal<ReadonlySet<string>>;      // ustawia FormRenderer
    readonly errors: WritableSignal<ReadonlyMap<string, string>>; // ustawia FormRenderer
    isReadOnly(field: FormField): boolean; // !!field.readOnly || readOnly().has(field.id)
    error(field: FormField): string | null;
  }
  ```

- [ ] **Step 1: Write failing tests** `validate-step.spec.ts`:
  - Zwraca błędy pól wymaganych na wszystkich poziomach (pole w SECTION → `repeatingSectionGrid`).
  - Pomija: id w `hidden`, potomków ukrytej sekcji (sekcja w `hidden`, dziecko nie), id w `readOnly`, `field.readOnly: true`, SECTION i TEXT_BLOCK.
- [ ] **Step 2: Write failing tests** w `form-renderer.spec.ts` (definicja testowa, nie mock: krok 1 z sekcją z TEXT_FIELD `imie` REQUIRED, TEXT_FIELD `nip` `['NIP']`, RADIO `czy` z opcjami Tak/Nie, i TEXT_FIELD `powod` REQUIRED ze stanem SHOW `"Tak" in …czy….__userAnswer`; krok 2 z jednym polem):
  - Klik „Dalej” na pustym kroku 1 → wciąż `Krok 1 z 2`, widać `Uzupełnij to pole` przy `imie`, `document.activeElement` to input pola `imie` (`[data-field-id="<id>"] input`).
  - Wpisanie wartości w `imie` usuwa komunikat bez ponownego klikania. Wpisanie `123` w `nip` pokazuje `Wpisz poprawny NIP: 10 cyfr`.
  - Wybór `Tak` w `czy` (przy włączonym trybie błędów) → po ewaluacji widać `Uzupełnij to pole` przy `powod`. Wybór `Nie` → `powod` znika, a jego błąd nie blokuje: po uzupełnieniu `imie` i poprawnym NIP (`1234563218`) „Dalej” przechodzi do kroku 2.
  - „Dalej” przed pierwszą ewaluacją (evaluator wstrzymany przez istniejący mechanizm `impl`) z uzupełnionym `imie` przechodzi dalej (`powod` jest w `initiallyHidden`).
  - „Wstecz” z kroku 2 nie pokazuje błędów na kroku 1. „Przerwij wypełnianie” po nieudanym „Dalej” usuwa komunikaty.
- [ ] **Step 3:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 4: Implement.**
  - `FormRenderer`: `providers: [AnswersStore, FormState]`. Sygnał `showErrorsFor = signal<number | null>(null)` (indeks strony). `computed` błędów: gdy `showErrorsFor() === index()`, `validateStep(page().questions, store.snapshot() /* czytaj store.version() */, hidden(), readOnlyIds())`, w przeciwnym razie pusta mapa. `effect` przepisuje ten computed i `readOnlyIds` do `FormState` (jedyne miejsce zapisu).
  - `next()` (przycisk „Dalej” woła `next()` zamiast `go(index()+1)`): licz `validateStep` od razu. Pusta → `showErrorsFor.set(null)`, `go(index()+1)`. Niepusta → `showErrorsFor.set(index())` i `afterNextRender`: pierwszy w kolejności dokumentu `[data-field-id]` z id w błędach, w nim pierwszy `input, select, textarea, button` bez `disabled` → `focus()`, `scrollIntoView({ block: 'center' })` (z `?.` dla jsdom).
  - `go()` (Wstecz) i `abort()` ustawiają `showErrorsFor.set(null)`. Zmiana definicji też.
- [ ] **Step 5:** Uruchom testy. Oczekiwane: PASS. (Pola nie renderują jeszcze błędów z `FormState`; testy z kroku 2 asercji tekstu potrzebują Task 5. **Dlatego w tym tasku** dodaj minimalne renderowanie błędu tylko w `TextFieldType` (`[error]="error()"` z `FormState`) i `RadioField`. Pełne pokrycie typów jest w Task 5.)
- [ ] **Step 6: Commit** `feat(preview): block Dalej on invalid fields and focus the first error`

---

### Task 4: Combobox i podpowiedź w shared/ui

**Files:**
- Create: `frontend/src/app/shared/ui/field-tooltip/field-tooltip.ts`, `field-tooltip.spec.ts`, `field-tooltip.stories.ts` (`UI/FieldTooltip`)
- Modify: `frontend/src/app/shared/ui/combobox/combobox.ts`, `combobox.spec.ts`, `combobox.stories.ts`
- Modify: `frontend/src/app/shared/ui/text-field/text-field.ts`, `text-field.stories.ts`

**Interfaces:**
- Produces:
  ```ts
  // field-tooltip.ts — selector 'app-field-tooltip'
  text = input.required<string>();   // HTML jak description (innerHTML)
  label = input.required<string>();  // etykieta pola do aria-label
  // renderuje: <button type="button" aria-label="Więcej informacji: {label}" [attr.aria-expanded] [attr.aria-controls]> ikona i </button>
  //            panel z tekstem (id 'app-field-tooltip-<n>'), widoczny gdy rozwinięty
  // combobox.ts — nowe wejścia
  error = input<string>();
  readonly = input(false);
  tooltip = input<string>();
  tag = input<string>();            // np. 'dane z rejestru'
  // text-field.ts — nowe wejścia
  tooltip = input<string>();
  tag = input<string>();
  ```
  `tag`: widoczny `<span class="ml-auto text-fg-muted text-label font-normal">` w wierszu etykiety (etykieta jako `flex`), a w `<label>` dodatkowo `<span class="sr-only">, {tag}</span>`, żeby był częścią nazwy dostępnej. Przycisk podpowiedzi stoi obok etykiety, **poza** elementem `<label>`. Panel jest pod wierszem etykiety.

- [ ] **Step 1: Write failing tests**
  - `field-tooltip.spec.ts`: przycisk ma `aria-label="Więcej informacji: Numer PESEL"`, `aria-expanded="false"`, panel ukryty. Klik → `aria-expanded="true"`, panel widoczny z tekstem, `aria-controls` wskazuje id panelu. Drugi klik zwija. `Escape` przy fokusie na przycisku zwija.
  - `combobox.spec.ts`: `error="Wybierz jedną z opcji"` → input `aria-invalid="true"`, `aria-describedby` zawiera id elementu z tym tekstem (obok `describedBy` z zewnątrz), klasa `border-danger`. `readonly` → `ArrowDown` i klik nie otwierają listy, brak przycisku ✕ przy wartości, input `readonly`. `tag="dane z rejestru"` → nazwa dostępna inputu (`label` z `for`) zawiera `dane z rejestru`. `tooltip="…"` → jest przycisk `Więcej informacji: Kraj`.
  - Text-field: story/play lub spec: `tag` i `tooltip` jak wyżej.
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 3: Implement.** Combobox w trybie `readonly`: klasy jak `text-field` readonly (`border-transparent bg-surface-readonly`), bez chevrona.
- [ ] **Step 4:** Stories: `UI/FieldTooltip` (zwinięty, rozwinięty przez play), `UI/Combobox` + warianty `ZBledem`, `TylkoDoOdczytu`, `TextField` + `ZRejestru`. Uruchom unit i `npm run test:storybook`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(ui): add field tooltip and error/read-only states to combobox`

---

### Task 5: Pola podglądu — błędy, tylko do odczytu, podpowiedź, rejestr

**Files:**
- Modify: `frontend/src/app/features/preview/fields/field-base.ts` i wszystkie pola: `text.ts`, `textarea.ts`, `date.ts`, `select.ts`, `dictionary-cascade.ts`, `radio.ts`, `checkbox.ts`, `consent-section.ts`, `file-uploader.ts`
- Modify: `frontend/src/app/features/preview/fields.stories.ts`
- Test: `frontend/src/app/features/preview/fields/fields-state.spec.ts` (nowy)

**Interfaces:**
- Consumes: `FormState` (Task 3), `app-field-tooltip`, wejścia `error/readonly/tooltip/tag` comboboxa i text-field (Task 4).
- Produces w `FieldBase`:
  ```ts
  protected readonly formState = inject(FormState);
  protected readonly error = computed(() => this.formState.error(this.field()));
  protected readonly readOnly = computed(() => this.formState.isReadOnly(this.field()));
  protected readonly errorId = computed(() => this.id() + '-error');
  protected readonly tooltip = computed(() => this.field().tooltipMessage?.trim() || undefined);
  protected readonly tag = computed(() => this.field().defaultValueType === 'EXTERNAL_SYSTEM' ? 'dane z rejestru' : undefined);
  // describedBy łączy descId i errorId (oba tylko gdy istnieją)
  ```

- [ ] **Step 1: Write failing tests** `fields-state.spec.ts`: dla każdego typu (TEXT_FIELD, NUMBER, TEXTAREA, DATEPICKER, SELECT, kaskada TERYT, RADIO, CHECKBOX bez opcji i z opcjami, CONSENT_SECTION, FILE_UPLOADER) host z `AnswersStore` i `FormState`, w którym `errors` ustawione na `{id: 'X'}`:
  - Tekst `X` jest widoczny, a element sterujący (input/radio/checkbox/przycisk pliku) ma `aria-invalid="true"` i jego `aria-describedby` (lub grupy — dla RADIO/CHECKBOX z opcjami/CONSENT na `fieldset`) zawiera id elementu z `X`.
  - `readOnly` ustawione na `{id}`: input `readonly` (TEXT/NUMBER/TEXTAREA/DATE), combobox nie otwiera listy, radio/checkbox/przycisk pliku `disabled`.
  - `tooltipMessage: 'Pomoc'` → przycisk `Więcej informacji: <etykieta>` (nie dla CONSENT_SECTION).
  - `defaultValueType: 'EXTERNAL_SYSTEM'` → widoczny tekst `dane z rejestru` i jest on częścią nazwy dostępnej pola (TEXT_FIELD: `getByLabelText(/dane z rejestru/)`).
  - Kaskada: błąd przy pierwszym pustym poziomie (`['mazowieckie']` → komunikat pod comboboxem `Powiat`).
- [ ] **Step 2:** Uruchom testy. Oczekiwane: FAIL.
- [ ] **Step 3: Implement** według Interfaces i spec „Pola”. Usuń tymczasowe wiązania z Task 3 na rzecz wspólnego `FieldBase`. RADIO/CHECKBOX z opcjami/CONSENT: błąd pod `fieldset`, `aria-describedby` grupy zawiera `errorId`, każde pole wyboru ma `aria-invalid`. FILE_UPLOADER: błąd pod ramką, `aria-describedby` przycisku zawiera `errorId`.
- [ ] **Step 4:** Story `Podgląd/Pola`: dodaj warianty `ZBledami` (FormState z błędami dla kilku typów), `TylkoDoOdczytu` (stan READ_ONLY), `ZPodpowiedzia` (`tooltipMessage`), pole z rejestru. Uruchom unit i `npm run test:storybook`. Oczekiwane: PASS.
- [ ] **Step 5: Commit** `feat(preview): show errors, read-only state, tooltips and registry tag on fields`

---

### Task 6: Walidatory w mockach

**Files:**
- Modify: `frontend/src/app/features/import/mock-forms/nadplata-podatku.json`, `numer-porzadkowy.json`
- Modify: `frontend/src/app/features/preview/form-renderer.spec.ts` (scenariusz na mocku) i ewentualnie testy, które przechodzą przez krok 1 mocka

**Interfaces:**
- Consumes: wszystko powyżej.

- [ ] **Step 1:** Jednorazowy skrypt (w scratchpadzie, niecommitowany) według spec „Doprecyzowania” pkt 1 i reguł 1–3: ustawia `validation` w obu mockach, zachowując formatowanie JSON (wcięcie 4 spacje jak w plikach). `git diff --stat` ma pokazywać tylko te dwa pliki i tylko linie `validation`.
- [ ] **Step 2: Write test** w `form-renderer.spec.ts` na `nadplata-podatku.json`:
  - Mock ma `REQUIRED, NIP` na `nip`, `REQUIRED, ZIP_CODE` na `kod_pocztowy`, `EMAIL` na `adres_e_mail`, `REQUIRED` na `kwota`, brak walidatorów na `numer_lokalu` (asercje na danych).
  - „Dalej” na kroku 1 → zostaje, fokus na pierwszym błędnym polu w kolejności DOM. Pola z rejestru (`kod_pocztowy = 00-001`) nie mają błędu.
- [ ] **Step 3:** Uruchom wszystkie testy; testy, które przechodzą przez krok 1 mocka i teraz się zatrzymują, uzupełniają wymagane pola (spec „Doprecyzowania” pkt 9). Oczekiwane: PASS, także `npm run test:storybook`.
- [ ] **Step 4: Commit** `feat(import): add backend-style validators to mock forms`
