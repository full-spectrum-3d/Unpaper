# Renderer formularza — krok 2a: słowniki

Data: 2026-11-21 · Gałąź: `feat/form-renderer-dictionaries` · Poprzedni krok: `2026-11-21-form-renderer-skeleton-design.md`

## Po co

Podgląd formularza na ekranie wyniku ma wyglądać i działać jak formularz COI z makiet. Obecnie każde pole `SELECT` ze słownikiem (`dictionaryName`) pokazuje tylko „Wybierz” i wyłączoną pozycję „Słownik: <nazwa>”. Backend dla słowników predefiniowanych zwraca same metadane, bez pozycji (`GET /dictionaries`), więc jury nie zobaczy, jak działa adres: Kraj z domyślną „Polska” i zależne listy województwo → powiat → gmina → miejscowość.

Sukces: na mockach „Nadpłata podatku” i „Numer porządkowy” adres działa jak na makiecie `wymagania/obrazy/standardy/p-012-003.png` i ekranie `nadplata/03.png`. Kraj ma „Polska” z ✕, pod nim „Województwo — Wybierz”. Po wyborze pojawia się kolejny poziom. Zmiana kraju na inny ukrywa TERYT (istniejące stany SHOW).

## Cele

- Dane przykładowe słowników we froncie (spec §9.2 `dictionaries.mock.ts`): Kraje, TERYT (drzewo), NUMERY_KIERUNKOWE.
- Komponent combobox (wzorzec ARIA 1.2) z filtrowaniem i przyciskiem ✕, używany przez wszystkie pola `SELECT`.
- Pole TERYT jako kaskada do 4 comboboxów w jednym polu.
- Stories w Storybooku i testy jednostkowe.

## Poza zakresem (kolejne kroki)

- Walidatory, blokada „Dalej”, fokus na pierwszym błędzie, READ_ONLY ze `states`, `tooltipMessage`, „dane z rejestru” (krok 2b).
- Pobieranie słowników z backendu (backend nie ma pozycji).
- Słowniki w polach RADIO/CHECKBOX (dokument „Słowniki” dopuszcza, ale mocki ich nie używają).
- Wielokrotny wybór w SELECT.

## Anty-cele

- Combobox niedostępny z klawiatury albo dla czytnika ekranu. Testy a11y w Storybooku są ustawione na `error` i muszą przechodzić.
- Rozjazd wyglądu między polem z wyszukiwaniem i bez wyszukiwania. Na makiecie Kraj i Województwo wyglądają tak samo.
- Kaskada, w której wybór województwa prowadzi do pustej listy powiatów.

## Ograniczenia

- Angular 22, standalone, sygnały, `input()/model()`, `inject()`, natywny control flow, Tailwind 4 z tokenami semantycznymi (`frontend/src/styles/tokens.css`), motyw `preview`.
- Bez nowych zależności (żadnej biblioteki comboboxa).
- Wartości odpowiedzi muszą działać z istniejącymi zapytaniami jsonata, np. `"Polska" in …kraj….field.__userAnswer`. Odpowiedź Kraju zostaje stringiem.

## Podejścia (wybrane: A)

- **A. Kaskada + własny combobox z wyszukiwaniem** (wybrane przez użytkownika). Najwierniejsze makietom, `searchEnabled` jest respektowane. Koszt: osobny komponent z pełną obsługą klawiatury.
- B. Kaskada na natywnych `<select>`. Szybko i dostępnie, ale bez wyszukiwania i ✕. Przy ~200 krajach niewygodne.
- C. TERYT jako jeden select województw. Najtaniej, ale niezgodne ze standardem („elementy zależne, następujące po sobie”).

## Projekt

### Dane: `features/preview/dictionaries.mock.ts`

```ts
export interface DictionaryNode { name: string; children?: DictionaryNode[] }
export interface Dictionary { levels: string[]; items: DictionaryNode[] }
export const SAMPLE_DICTIONARIES: Record<string, Dictionary>;
export function findDictionary(name: string | undefined): Dictionary | undefined;
```

- `Kraje`: `levels: ['Kraj']`, pełna lista państw po polsku, posortowana, z „Polska”.
- `TERYT_4G_DOWODOWY`: `levels: ['Województwo','Powiat','Gmina','Miejscowość']`. Wszystkie 16 województw. Każde ma co najmniej jedną pełną gałąź do miejscowości (miasto wojewódzkie: powiat → gmina → miejscowość). Mazowieckie i małopolskie mają po 2–3 powiaty, żeby filtrowanie miało co pokazać.
- `TERYT_DOWODOWY`: te same dane co `TERYT_4G_DOWODOWY` (moja decyzja: wzorce różnią się tylko nazwą, spec D13; dane wspólne).
- `NUMERY_KIERUNKOWE`: `levels: ['Numer kierunkowy']`, ok. 10 pozycji w formacie `+48 Polska`.
- Pole `options` w JSON-ie ma pierwszeństwo: jeśli jest niepuste, używamy go zamiast słownika.
- Nieznana `dictionaryName` bez `options`: combobox pusty, w liście komunikat „Brak pozycji w słowniku <nazwa>” (zastępuje dzisiejszą opcję „Słownik: …”).

### Combobox: `shared/ui/combobox/combobox.ts`

Generyczny komponent UI, bez wiedzy o formularzach.

- API: `value = model<string>('')`, `options = input.required<string[]>()`, `label = input.required<string>()`, `labelHidden`, `searchable = input(false)`, `placeholder = input('Wybierz')`, `describedBy = input<string|null>(null)`, `emptyText = input('Brak wyników')`, `inputId`.
- Wzorzec ARIA 1.2 combobox: `input role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `aria-autocomplete="list"` gdy `searchable`. Lista `role="listbox"` z `role="option"` i `aria-selected`.
- `searchable=false` to wariant „select-only”: input `readonly`, bez filtrowania, ten sam wygląd.
- Klawiatura: ↓/↑ otwiera listę i przesuwa aktywną opcję, Home/End, Enter wybiera, Escape zamyka (drugi Escape przy zamkniętej liście czyści tekst filtra), Tab zamyka bez zmiany wartości.
- Mysz: klik w pole albo w chevron otwiera, klik w opcję wybiera, klik poza zamyka (`(document:pointerdown)` w `host`).
- Filtrowanie: `includes` bez rozróżniania wielkości liter i polskich znaków (`normalize('NFD')`, usunięcie znaków diakrytycznych; „ł” mapowane na „l”). Po zamknięciu tekst wraca do wybranej wartości.
- ✕ widoczny tylko przy wybranej wartości, `button` z `aria-label="Wyczyść: <label>"`, ustawia `''` i oddaje fokus inputowi.
- Wygląd jak `text-field` (te same klasy obramowania, paddingu i fokusu), chevron po prawej. Lista pod polem, `max-h` z przewijaniem, aktywna opcja podświetlona tokenem. Brak wirtualizacji (~200 pozycji).
- Stories: `UI/Combobox`, warianty: domyślny, z wartością, wyszukiwanie, pusty, długa lista.

### Pole SELECT: `features/preview/fields/select.ts`

- Pole bez drzewa (Kraje, NUMERY_KIERUNKOWE, `options`) renderuje jeden `app-combobox`. Wartość to istniejąca odpowiedź-string.
- `searchable = field.searchEnabled === true || options.length > 20`. Moja decyzja: w `numer-porzadkowy.json` `searchEnabled` jest `null`, a ~200 krajów bez filtrowania jest nieużywalne.
- Etykietę renderuje combobox (`<label for>` przy inpucie): `label` = etykieta z `FieldBase`, `labelHidden` = brak `title`. Opis zostaje w polu i trafia do comboboxa przez `describedBy`.
- Do `FormField` dochodzą `searchEnabled?: boolean` i `multiLevelTree?: boolean`.

### Pole TERYT (kaskada): `features/preview/fields/dictionary-cascade.ts`

- Używane, gdy słownik ma więcej niż jeden poziom (`levels.length > 1`). Moja decyzja: decyduje słownik, nie flaga `multiLevelTree`, bo flaga jest niespójna w referencjach (`false` w części pól TERYT), a standard wymaga zależnych list.
- `field-host` wybiera między `app-select-field` a `app-dictionary-cascade-field` według słownika.
- Odpowiedź: `string[]` (ścieżka, np. `['mazowieckie','Warszawa','Warszawa','Warszawa']`). `initialAnswer` zwraca `[]` dla takich pól (zgodnie z `defaultValue: []`). Gdy `defaultValue` jest niepuste, bierzemy je jako ścieżkę.
- Renderuje combobox poziomu 0 zawsze, a poziom i+1 tylko gdy poziom i ma wartość i wybrany węzeł ma dzieci.
- Etykiety: nazwy poziomów (`Województwo`, `Powiat`, …). `title` pola równy nazwie słownika (jak we wzorcach) nie jest pokazywany. Inny `title` staje się legendą grupy.
- Struktura: `div role="group"` z comboboxami jeden pod drugim, odstęp jak między polami siatki. Gdy `title` różni się od `dictionaryName`, grupa ma widoczny nagłówek (`title`) i `aria-labelledby`. W przeciwnym razie nagłówka nie ma, a każdy combobox ma własną etykietę poziomu (moja decyzja: na makiecie nad listami nie ma nagłówka).
- Zmiana wartości na poziomie i obcina ścieżkę do i+1 elementów (niższe poziomy się czyszczą).
- `searchable` na każdym poziomie według tej samej reguły co SELECT (`searchEnabled === true` albo więcej niż 20 pozycji na danym poziomie).

### Store i widoczność

- `initialAnswer`: pola kaskadowe → tablica, pozostałe SELECT bez zmian (pierwszy element `defaultValue`, czyli „Polska”).
- `reset()` przywraca ścieżkę `[]` i „Polska”. Jest pokryte, bo `reset` woła `initialAnswer`.
- jsonata: brak zmian. Zapytania mocków odwołują się tylko do Kraju (string).

## Testy

- Unit: filtr bez diakrytyków, klawiatura comboboxa (↓, Enter, Escape, Home/End), ✕ czyści i oddaje fokus, `options` mają pierwszeństwo przed słownikiem, kaskada obcina ścieżkę, poziom pojawia się po wyborze, `initialAnswer` dla kaskady, wszystkie 16 województw mają gałąź do miejscowości (test danych).
- Renderer: na mocku „Nadpłata” Kraj = „Polska”, widać „Województwo”. Po ✕ na Kraju TERYT znika.
- Storybook: stories comboboxa i zaktualizowane `Podgląd/Pola` (Kraj, TERYT). Testy a11y przechodzą.

## Zostawione builderowi

- Dokładne klasy Tailwind, ikony chevron/✕ (inline SVG jak w istniejących komponentach).
- Konkretne powiaty, gminy i miejscowości w danych przykładowych (prawdziwe nazwy).
- Podział komponentu comboboxa na pliki.
