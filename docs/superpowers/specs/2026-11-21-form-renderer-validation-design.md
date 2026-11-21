# Renderer formularza — krok 2b: walidacja, READ_ONLY, podpowiedzi, dane z rejestru

Data: 2026-11-21 · Gałąź: `feat/form-renderer-validation` · Poprzednie kroki: `2026-11-21-form-renderer-skeleton-design.md`, `2026-11-21-form-renderer-dictionaries-design.md`

## Po co

Podgląd na ekranie wyniku ma zachowywać się jak formularz COI, a nie tylko wyglądać jak on. Jury, klikając „Dalej” z pustymi lub błędnymi polami, ma zobaczyć, że wygenerowana konfiguracja (`validation`, `states`, `tooltipMessage`, `defaultValueType`) naprawdę działa. Spec techniczna §9.3 wymaga walidatorów po stronie klienta, fokusu na pierwszym błędzie, blokady pól `READ_ONLY` i oznaczenia „dane z rejestru”.

Sukces: na mocku „Nadpłata podatku” kliknięcie „Dalej” na pustym kroku 1 zostawia użytkownika na kroku i pokazuje błędy przy wymaganych polach. Fokus trafia na pierwsze błędne pole, a poprawienie pola od razu usuwa jego komunikat. Wpisanie `123` w NIP daje „Wpisz poprawny NIP: 10 cyfr”. Pola z rejestru mają etykietę „dane z rejestru”.

## Cele

- Walidatory z listy COI: `REQUIRED, EMAIL, PESEL, NIP, REGON, ZIP_CODE, EPUAP, ADE, SERIAL_NUMBER_ID_CARD`.
- „Dalej” blokuje przejście przy błędach na bieżącym kroku i ustawia fokus na pierwszym błędnym polu (kolejność w DOM).
- Stan `READ_ONLY` ze `states` (jsonata) blokuje pole, tak jak statyczne `readOnly`.
- `tooltipMessage` jako dostępna podpowiedź przy etykiecie.
- Oznaczenie „dane z rejestru” przy polach z `defaultValueType: EXTERNAL_SYSTEM`.
- Uzupełnione mocki (`frontend/src/app/features/import/mock-forms/*.json`) o walidatory, jakie wygenerowałby backend (wybór użytkownika: wariant A).

## Poza zakresem

- Podpięcie prawdziwego `/forms/convert` (osobny krok).
- Walidacja na stronie końcowej / „Wyślij” (renderer nie ma wysyłki).
- Walidatory spoza listy (telefon, regex KRS).
- Maski wprowadzania (np. `__-___` dla kodu pocztowego).
- Dodawanie do mocków stanów `READ_ONLY` i `tooltipMessage`. Ani wzorce COI, ani szablony backendu ich nie mają, więc pokazujemy je w Storybooku (moja decyzja: nie wymyślamy treści formularza).

## Anty-cele

- Błędy widoczne, zanim użytkownik spróbuje przejść dalej.
- Blokowanie przez pole, którego użytkownik nie widzi albo nie może zmienić (ukryte lub tylko do odczytu).
- Komunikat bez powiązania z polem dla czytnika ekranu (`aria-invalid` + `aria-describedby`).
- Rozjazd z backendem: te same kody walidatorów i te same typy pól, które je przyjmują (spec §7.3 R15).

## Ograniczenia

- Angular 22 jak dotąd (sygnały, `input()/model()`, `inject()`, bez `@HostListener`), bez nowych zależności.
- Istniejące: `AnswersStore` (odpowiedzi), `evaluateVisibility` (jsonata, fail-open, kolejka żądań w `FormRenderer`), `app-text-field` z wejściem `error`, `app-combobox`.
- Polskie komunikaty w trybie rozkazującym (standard: „Wpisz 10 cyfr.”), dokładnie jak w tabeli niżej.

## Podejścia (wybrane: A)

- **A. Czyste funkcje walidacji + stan formularza w serwisie komponentu** (wybrane). Walidacja przy „Dalej”, potem na bieżąco dla tego kroku. Pasuje do `AnswersStore` i jsonata, łatwo testowalne.
- B. Angular Signal Forms. Wymaga dynamicznego schematu z JSON-a i przepisania `AnswersStore`.
- C. Walidacja przy opuszczeniu pola (blur) i przy „Dalej”. Błędy pojawiają się, zanim użytkownik skończy, wbrew standardowi „przewiduj emocje użytkownika”.

## Projekt

### Walidatory: `features/preview/validators.ts`

```ts
export type ValidatorCode = 'REQUIRED' | 'EMAIL' | 'PESEL' | 'NIP' | 'REGON' | 'ZIP_CODE' | 'EPUAP' | 'ADE' | 'SERIAL_NUMBER_ID_CARD';
export function validateField(field: FormField, answer: unknown): string | null; // pierwszy błąd albo null
```

- Kolejność: najpierw `REQUIRED`, potem walidatory formatu w kolejności z `validation`. Walidatory formatu pomijają pustą wartość.
- Wartość tekstowa jest przycinana (`trim`). Dla PESEL, NIP i REGON przed sprawdzeniem usuwamy spacje i myślniki (moja decyzja: ludzie wpisują `123-456-32-18`).
- Nieznany kod: ignorowany, jedno `console.warn` na kod (fail-open, jak jsonata).
- Pusta odpowiedź według typu: `''`, `[]` (CHECKBOX, FILE_UPLOADER, kaskada TERYT), CONSENT_SECTION: którakolwiek zgoda z `required: true` ma `false`. Kaskada TERYT jest pusta, dopóki ścieżka nie dojdzie do liścia (wybrany węzeł bez `children`).
- Reguły (moja decyzja, gdzie spec mówi tylko nazwę):
  - PESEL: 11 cyfr, suma kontrolna wagi `1,3,7,9,1,3,7,9,1,3`, cyfra kontrolna `(10 - suma % 10) % 10`. Bez sprawdzania daty.
  - NIP: 10 cyfr, wagi `6,5,7,2,3,4,5,6,7`, `suma % 11` równe ostatniej cyfrze (wynik 10 = niepoprawny).
  - REGON: 9 cyfr (wagi `8,9,2,3,4,5,6,7`) albo 14 cyfr (wagi `2,4,8,5,0,9,7,3,6,1,2,4,8`). Kontrola `suma % 11`, 10 → 0.
  - ZIP_CODE: `^\d{2}-\d{3}$`.
  - EMAIL: `^[^\s@]+@[^\s@]+\.[^\s@]+$`.
  - EPUAP: `^/[^/\s]+/[^/\s]+$` (np. `/urzad/SkrytkaESP`).
  - ADE: `^AE:PL-\d{5}-\d{5}-[A-Z]{5}-\d{2}$` (bez rozróżniania wielkości liter).
  - SERIAL_NUMBER_ID_CARD: 3 litery + 6 cyfr (bez rozróżniania wielkości liter). Litery mają wartości A=10…Z=35, wagi `7,3,1,9,7,3,1,7,3`, a cyfra na pozycji 4 (indeks 3) jest kontrolna: `suma pozostałych % 10`.

Komunikaty (dokładnie):

| Kod / przypadek | Komunikat |
|---|---|
| REQUIRED: TEXT_FIELD, NUMBER, TEXTAREA, DATEPICKER | Uzupełnij to pole |
| REQUIRED: SELECT, RADIO, kaskada TERYT | Wybierz jedną z opcji |
| REQUIRED: CHECKBOX | Zaznacz to pole |
| REQUIRED: CONSENT_SECTION | Zaznacz wymaganą zgodę |
| REQUIRED: FILE_UPLOADER | Dodaj plik |
| PESEL | Wpisz poprawny numer PESEL: 11 cyfr |
| NIP | Wpisz poprawny NIP: 10 cyfr |
| REGON | Wpisz poprawny REGON: 9 lub 14 cyfr |
| ZIP_CODE | Wpisz kod w formacie 00-000 |
| EMAIL | Wpisz adres e-mail, np. jan@domena.pl |
| EPUAP | Wpisz adres skrytki ePUAP, np. /urzad/SkrytkaESP |
| ADE | Wpisz adres do e-Doręczeń, np. AE:PL-12345-67890-ABCDE-12 |
| SERIAL_NUMBER_ID_CARD | Wpisz serię i numer dowodu: 3 litery i 6 cyfr |

### Walidacja kroku: `features/preview/validate-step.ts`

```ts
export function validateStep(questions: Question[], answers: ReadonlyMap<string, unknown>,
  hidden: ReadonlySet<string>, readOnly: ReadonlySet<string>): Map<string, string>;
```

- Przechodzi pola rekurencyjnie (`repeatingSectionGrid`) w kolejności pytań. Pomija pola z `hidden`, z `readOnly` (stany) i ze statycznym `field.readOnly` oraz typy bez odpowiedzi (SECTION, TEXT_BLOCK).
- Kolejność mapy nie decyduje o fokusie (patrz niżej).

### Stany: `evaluateVisibility` → `evaluateStates`

- `visibility.ts` eksportuje `evaluateStates(def, answers): Promise<{ hidden: ReadonlySet<string>; readOnly: ReadonlySet<string> }>`. `READ_ONLY` jest prawdą, gdy którekolwiek zapytanie `READ_ONLY` zwraca `true` (fail-open: błąd zapytania = nie blokuj). `evaluateVisibility` zostaje jako cienka funkcja zwracająca `hidden` albo jest zastąpiona (decyzja buildera). Token `VISIBILITY_EVALUATOR` zmienia typ na `evaluateStates`. Testy wyścigu w `form-renderer.spec.ts` dostosować.
- Do `KNOWN_STATE_TYPES` (jeśli trzeba) dochodzi `READ_ONLY`.

### Stan formularza: `features/preview/form-state.ts`

Serwis komponentu (`@Injectable()`, dostarczany w `FormRenderer.providers` obok `AnswersStore`), żeby nie przeciągać wejść przez siatkę i sekcje:

```ts
readonly readOnly: Signal<ReadonlySet<string>>;      // ze stanów
readonly errors: Signal<ReadonlyMap<string, string>>; // widoczne komunikaty
isReadOnly(field: FormField): boolean;               // field.readOnly || readOnly().has(field.id)
error(field: FormField): string | null;
```

- `FormRenderer` ustawia `readOnly` po każdej ewaluacji stanów (`hidden` dalej idzie wejściem do siatki jak dziś).
- Błędy są pokazywane po pierwszej nieudanej próbie „Dalej” na danym kroku. Od tego momentu `errors` = `validateStep(…)` liczone na bieżąco (computed z `store.version()`, `hidden`, `readOnly`) dla tego kroku. Zmiana kroku (Dalej z sukcesem, Wstecz) i „Przerwij wypełnianie” czyszczą tryb pokazywania błędów.
- „Wstecz” nie waliduje.

### „Dalej” i fokus

- `go(index + 1)` z przycisku „Dalej” najpierw liczy `validateStep` dla bieżącej strony. Pusta mapa → przejście jak dziś (fokus na nagłówku kroku). Niepusta → zostaje na kroku, włącza pokazywanie błędów i po renderze (`afterNextRender`) ustawia fokus na pierwszym błędnym polu w kolejności DOM.
- Lokalizacja pola: `field-host` dostaje `[attr.data-field-id]="field().id"`. Fokus: pierwszy element `[data-field-id]` w kolejności dokumentu, którego id jest w błędach, a w nim pierwszy `input, select, textarea, button` niebędący `disabled`. Przewinięcie `scrollIntoView({ block: 'center' })`.
- Ewaluacja stanów jest asynchroniczna. „Dalej” używa ostatniego wyniku `hidden`/`readOnly` (moja decyzja; różnica jednej klatki jest bez znaczenia, bo użytkownik i tak widzi ten sam stan).

### Pola: błąd, tylko do odczytu, podpowiedź, rejestr

- `FieldBase` dostaje z `FormState`: `error = computed(...)`, `readOnly = computed(...)`, `errorId = id + '-error'`, `describedBy` łączy opis i błąd. Dochodzą też `tooltip` i `fromRegistry` (`defaultValueType === 'EXTERNAL_SYSTEM'`).
- Wygląd błędu jak w `app-text-field`: czerwona ramka (`border-danger`), pod polem `✕ <komunikat>` (`text-danger`), `aria-invalid="true"`, komunikat w `aria-describedby`.
  - TEXT_FIELD / NUMBER: istniejące `error` i `readonly` w `app-text-field`.
  - TEXTAREA, DATEPICKER: ten sam wzorzec we własnym szablonie.
  - SELECT, kaskada TERYT: `app-combobox` dostaje wejścia `error = input<string>()` i `readonly = input(false)`. Tryb `readonly`: input `readonly`, lista się nie otwiera, brak ✕, tło `bg-surface-readonly` i `border-transparent` jak pole tekstowe. Kaskada: błąd przy pierwszym pustym poziomie.
  - RADIO, CHECKBOX, CONSENT_SECTION: błąd pod grupą. Grupa (`fieldset`/`role="radiogroup"`) ma `aria-describedby` na błąd, a każde pole wyboru ma `aria-invalid`. Tylko do odczytu: `disabled` na kontrolkach (moja decyzja: radio nie obsługuje `readonly`).
  - FILE_UPLOADER: błąd pod ramką, `aria-describedby` na przycisku „Dodaj lub przeciągnij plik”. Tylko do odczytu: przycisk `disabled`.
- **Podpowiedź (`tooltipMessage`)**: przycisk ikonki „i” obok etykiety (`aria-label="Więcej informacji: <etykieta>"`, `aria-expanded`), który rozwija tekst podpowiedzi pod etykietą (wzorzec disclosure, nie dymek na hover, bo musi działać z klawiatury i na dotyku). Tekst traktowany jak opis (może zawierać HTML jak `description`, renderowany tym samym sposobem).
- **„dane z rejestru”**: mały tekst `text-fg-muted` po prawej stronie etykiety (jak na szkicu), widoczny przy każdym polu `EXTERNAL_SYSTEM`, także edytowalnym (np. e-mail, kod pocztowy). Dla czytników ekranu w etykiecie jako `<span class="sr-only">, </span>dane z rejestru`, czyli część nazwy pola.

```
Numer PESEL  ⓘ                           dane z rejestru
[ 51051101608                                       ]   ← tylko do odczytu, szare
Kwota
[                                                   ]   ← czerwona ramka
✕ Uzupełnij to pole
```

### Mocki: walidatory jak z backendu

- Do obu plików mock-forms dodajemy `validation` według reguły (moja decyzja, odtwarza backend `build/`):
  1. Pole, którego `techName` występuje w `backend/app/resources/templates/*.json`, dostaje `validation` z szablonu (np. NIP, PESEL, kod pocztowy, e-mail).
  2. Pozostałe pola wejściowe (TEXT_FIELD, NUMBER, TEXTAREA, SELECT, RADIO, DATEPICKER, FILE_UPLOADER) poza `readOnly` dostają `REQUIRED`, chyba że tytuł zawiera „(opcjonalnie)” albo szablon backendu dla tego `techName` nie ma `REQUIRED` (np. numer lokalu, telefon).
  3. CONSENT_SECTION: bez zmian (wymagalność wynika z `consents[].required`).
- Pliki referencyjne w `wymagania/` zostają nietknięte.
- Testy, które ładują mocki (np. renderer, import), muszą dalej przechodzić.

## Testy

- `validators.spec.ts`: każdy walidator z poprawnym i błędnym przykładem. PESEL `44051401458` poprawny, `44051401459` błędny. NIP `1234563218` poprawny, `1234563219` błędny. REGON `123456785` poprawny (9), REGON `12345678901235` poprawny (14), `12345678901234` błędny. Dowód `ABA300000` poprawny (suma kontrolna), `ABA300001` błędny. Puste pole z walidatorem formatu i bez REQUIRED = brak błędu. Kolejność REQUIRED przed formatem. Nieznany kod ignorowany. Kaskada TERYT bez liścia = „Wybierz jedną z opcji”.
- `validate-step.spec.ts`: pomija ukryte, tylko do odczytu (stan i statyczne), zagnieżdżone pola w sekcjach są sprawdzane.
- `visibility.spec.ts`: `READ_ONLY` z zapytaniem prawdziwym/fałszywym/błędnym (fail-open).
- `form-renderer.spec.ts` na mocku „Nadpłata”: „Dalej” na pustym kroku 1 → nadal krok 1, komunikat „Uzupełnij to pole” widoczny, `document.activeElement` to input pierwszego błędnego pola. Uzupełnienie pola usuwa jego komunikat bez ponownego klikania. „Wstecz” nie waliduje. „Przerwij wypełnianie” czyści błędy.
- Combobox: `error` daje `aria-invalid` i komunikat w `aria-describedby`, a `readonly` blokuje otwieranie i ✕.
- Storybook (`Podgląd/Pola`): story z błędami, z `READ_ONLY` (stan), z `tooltipMessage` i z polem z rejestru. Testy a11y przechodzą.

## Zostawione builderowi

- Czy `evaluateVisibility` zostaje jako wrapper, czy znika.
- Ikona „i” (inline SVG) i dokładne klasy.
- Podział `FieldBase` na mniejsze części, jeśli urośnie.

## Doprecyzowania po przeglądzie buildera (moje decyzje)

1. **Dopasowanie mocków do szablonów backendu.** Robi to jednorazowy skrypt (nie commitujemy go). Commitujemy tylko zaktualizowane JSON-y. W `techName` szablonu `{sfx}` oznacza `''`, `_siedziba` albo `_inna_osoba`. Szablony z innymi placeholderami (`{field_tech_name}`, `{section_tech_name}`) są pomijane. Dopasowanie jest dokładne po podstawieniu. Wynik dla obu mocków:
   - `kraj*`, `wojewodztwo*`, `miejscowosc*_zagranica`, `kod_pocztowy*_zagranica`, `ulica*_zagranica`, `ulica*`, `numer_budynku*`: `REQUIRED`.
   - `kod_pocztowy*` (krajowy): `REQUIRED, ZIP_CODE`.
   - `numer_lokalu*`, `numer_telefonu`, `numer_krs`: bez walidatorów.
   - `adres_e_mail`: `EMAIL`.
   - `nazwa`: `REQUIRED`. `nip`: `REQUIRED, NIP`. `regon`: `REQUIRED, REGON`.
   - `imie`, `nazwisko`, `numer_pesel`: z szablonu (`REQUIRED`, `PESEL`), ale są `readOnly`, więc nie są walidowane.
   - Pozostałe pola wejściowe poza `readOnly` (np. `kwota`, `uzasadnienie`, `numer_rachunku`, `obreb_numer`, `potwierdzenie_przelewu`): `REQUIRED` według reguły 2.
2. **NIP i „dane z rejestru” są osiągalne na „Nadpłacie”.** Sekcja „Dane podmiotu” ma pole `nip` (widoczne po wyborze „Osoby prawnej…”). Pola `EXTERNAL_SYSTEM` to imię, nazwisko, PESEL, kod pocztowy, ulica, numer budynku, numer lokalu, telefon i e-mail. Wartości testowe z `SAMPLE_REGISTRY_DATA` spełniają walidatory (`00-001`, `jan.kowalski@example.com`), więc prefill nie blokuje „Dalej”.
3. **Brak instancji powtarzanych.** Każde pole ma unikalne `id` (UUID), a renderer rysuje je raz (`REPEATING_SECTION` nie występuje w mockach). Klucz błędów to `field.id`.
4. **„Dalej” przed pierwszą ewaluacją** używa tego samego `hidden()` co widok (`evaluated ?? initiallyHidden`) i pustego `readOnly`.
5. **Tryb błędów obejmuje tylko bieżący krok i jest liczony na bieżąco.** Pole wymagane, które pojawi się po zmianie odpowiedzi (SHOW), od razu pokazuje błąd, bo tryb jest już włączony.
6. **Pustość**: NUMBER i DATEPICKER są przechowywane jako string (pole tekstowe), pusty = `''` po `trim`. `'0'` to poprawna wartość.
7. **Konsumenci komponentów:** `app-text-field` używa też logowanie. Nowe wejścia comboboxa (`error`, `readonly`) mają wartości domyślne (`undefined`, `false`), więc istniejące użycia się nie zmieniają. Story `UI/Combobox` dostaje warianty z błędem i tylko do odczytu.
8. **Podpowiedź i „dane z rejestru” w polach grupowych.** RADIO, CHECKBOX i FILE_UPLOADER umieszczają je przy legendzie lub etykiecie grupy. CONSENT_SECTION nie ma tytułu, więc ich nie pokazuje. „dane z rejestru” w grupie jest częścią legendy (sr-only przecinek jak wyżej).
9. **Testy wolno aktualizować.** Testy klikające „Dalej” na mocku z pustymi polami (np. przejście na krok 2) uzupełniają wymagane pola albo używają definicji testowej bez walidatorów. Testy wyścigu dostosowujemy do `evaluateStates`.
