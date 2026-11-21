# Ekran wyniku — zakładka „Raport”

Data: 2026-11-21 · Gałąź: `feat/result-report` · Spec techniczna: §6.2 (raport konwersji), §9.1 (widok Wynik)

## Po co

Jury ma zobaczyć nie tylko wynikowy formularz, ale też co system zrobił z dokumentem: jaką metodą wyciągnął tekst (OCR, PDF, DOCX), jaki model przeanalizował treść, które reguły autonaprawa poprawiła, jakie ostrzeżenia zostały i jakie słowniki proponuje. Spec §9.1 wymaga na ekranie wyniku trzech zakładek: **Podgląd formularza**, **JSON**, **Raport**, przy czym ostrzeżenia mają link do miejsca w JSON-ie (wybór użytkownika: pełny link, wariant A).

Sukces: po przetworzeniu pliku zakładka „Raport” pokazuje ostrzeżenia, poprawki, propozycje słowników, statystyki i przebieg przetwarzania. Klik „Pokaż w JSON” przy pozycji ze ścieżką przełącza na zakładkę JSON, przewija do fragmentu, podświetla go i ustawia na nim fokus.

## Cele

- Front prosi o raport (`POST /forms/convert?report=true` → `{ form, report }`) i trzyma go w wierszu kolejki obok formularza.
- Zakładki na ekranie wyniku zgodne ze wzorcem ARIA tabs.
- Widok raportu z sekcjami w kolejności: Ostrzeżenia, Poprawki autonaprawy, Propozycje słowników, Statystyki, Przetwarzanie.
- Widok JSON z mapą ścieżka → linie, podświetleniem i przewinięciem.
- Mock konwersji z przykładowym raportem.

## Poza zakresem

- Raport w ZIP-ie i osobny przycisk „Pobierz raport” (użytkownik może poprosić później).
- Drzewo JSON z rozwijaniem węzłów.
- Edycja propozycji słowników.

## Anty-cele

- Zmiana zawartości plików do pobrania: ZIP i „Pobierz .json” dalej zawierają sam formularz w formacie importu.
- Utrata odpowiedzi wpisanych w podglądzie przy przełączaniu zakładek (podgląd zostaje zamontowany, jak dziś).
- Martwy link: link pokazujemy tylko wtedy, gdy ścieżka istnieje w JSON-ie formularza.

## Ograniczenia

- Angular 22 (sygnały, `input()`, `inject()`, natywny control flow, `host: {}`), NgRx, Tailwind 4 z tokenami, bez nowych zależności.
- Raport to dane z sieci: typujemy go luźno i każde pole czytamy defensywnie (brakujące pola nie wywracają widoku).
- Ścieżki w raporcie mają dwa źródła. Część dotyczy wynikowego JSON-a (np. `tabs[1].questions[0]`, `tabs[0].questions[2].field.repeatingSectionGrid[1]`). Część dotyczy szkicu LLM, który nie trafia do wyniku (np. `subject_pages[0].sections[1].fields[2]`, `chunk[3]`, `title`, `authority_name`). Ścieżka może też wskazywać element, który autonaprawa usunęła (`tabs[2]` przy „Usunięto pustą stronę”).

## Podejścia (wybrane: A)

- **A. Raport osobno w kolejce + własny formatter JSON z mapą ścieżek** (wybrane). ZIP i podgląd bez zmian, link precyzyjny.
- B. Osobne żądanie po raport. Odpada: backend zwraca oba w jednej odpowiedzi.
- C. `{form, report}` w `result`. Odpada: zepsułoby ZIP, pobieranie i podgląd.
- Dla linku: D. drzewo JSON (dużo pracy przy tym samym efekcie), E. wyszukiwanie fragmentu w tekście (niejednoznaczne przy powtarzających się kluczach). Oba odrzucone.

## Projekt

### Dane

- `ConvertFileFn` zwraca `Observable<ConvertResult>`, gdzie `ConvertResult = { form: unknown; report: unknown | null }`.
  - HTTP: `convertApiV1FormsConvertPost({ report: true, body })`. Odpowiedź ma kształt `{ form, report }`. Jeśli odpowiedź nie ma klucza `form` (np. starszy backend), cała odpowiedź to formularz, a `report = null`.
  - Mock: zwraca `{ form, report }` z przykładowym raportem (`frontend/src/app/features/import/mock-report.ts`) dopasowanym do zwracanego mocka. Ma co najmniej jedno ostrzeżenie i jedną poprawkę ze ścieżkami istniejącymi w mocku, jedno ostrzeżenie ze ścieżką szkicu (bez linku), jedną propozycję słownika, `extraction.method: "pdf_text"`, model, czasy.
- `QueueItem.report: unknown | null`. `convertSucceeded` dostaje `report`. Pozostałe miejsca, które tworzą `QueueItem` (dodawanie plików, fixture'y testów i stories), ustawiają `report: null`.
- `result` dalej zawiera sam formularz. ZIP i pobieranie bez zmian.

### Model raportu: `features/result/report.ts`

```ts
export interface ReportIssue { code: string; message: string; path?: string }
export interface ConversionReport {
  sourceFile?: { name?: string; mime?: string; sizeBytes?: number; pages?: number | null; decrypted?: boolean };
  extraction?: { method?: string; convertedToOpenXml?: boolean; ocrMeanConfidence?: number | null; blocks?: number };
  llm?: { model?: string | null; durationMs?: number; retries?: number; fallback?: boolean; fallbackReason?: string | null; ruleBasedDraft?: boolean };
  stats?: { tabs?: number; sections?: number; fields?: number; states?: number };
  dictionaryProposals?: { name: string; title?: string; items?: unknown[]; usedBy?: string[] }[];
  warnings?: ReportIssue[];
  fixes?: ReportIssue[];
  timings?: Record<string, number>;
  durationMs?: number;
}
export function asReport(value: unknown): ConversionReport | null; // obiekt → raport, reszta → null; tablice, które nie są tablicami, traktuje jak puste
```

### Formatter JSON z mapą ścieżek: `features/result/json-lines.ts`

```ts
export interface JsonLines { lines: string[]; ranges: ReadonlyMap<string, { start: number; end: number }> }
export function formatJson(value: unknown): JsonLines;
```

- Wynik `lines.join('\n')` jest identyczny z `JSON.stringify(value, null, 2)`.
- `ranges` ma wpis dla każdej wartości obiektu i tablicy. Klucz ma składnię backendu: `a.b[0].c` (klucze kropką, indeksy w nawiasach, bez wiodącej kropki). `start` to linia z kluczem lub otwarciem wartości, `end` to linia zamknięcia (0-based, włącznie).
- `resolve(path)`: ścieżkę z raportu sprawdzamy dokładnie w `ranges`. Jeśli jej nie ma, link nie jest pokazywany (bez dopasowań przybliżonych).

### Ekran wyniku: zakładki

- `role="tablist"` z `aria-label="Widok wyniku"` i trzema `role="tab"`: „Podgląd formularza”, „JSON”, „Raport”. Aktywna ma `aria-selected="true"` i `tabindex="0"`, pozostałe `tabindex="-1"`. Strzałki ←/→ przenoszą fokus i aktywują sąsiednią zakładkę (z zawijaniem), Home/End pierwszą/ostatnią (automatyczna aktywacja).
- Panele `role="tabpanel"` z `aria-labelledby`. Panel podglądu zostaje w DOM (`hidden`), żeby nie gubić odpowiedzi. Panele JSON i Raport mogą być renderowane warunkowo.
- Domyślna zakładka: Podgląd, gdy wynik jest formularzem, w przeciwnym razie JSON (jak dziś). Gdy wynik nie jest formularzem, zakładka „Podgląd formularza” jest ukryta.
- „Pobierz .json” zostaje w nagłówku karty.

### Widok JSON

- Linie renderowane w `<pre>` jako bloki `<span>` z numerem linii w `data-line`. Zakres podświetlony ma klasę tła `bg-warning-subtle`.
- Kontener ma `role="region"`, `aria-label="Wynik konwersji w formacie JSON"`, `tabindex="0"`, jak dziś.
- Pokazanie ścieżki: przełączenie na zakładkę JSON, po renderze `scrollIntoView({ block: 'center' })` na pierwszej linii zakresu i fokus na elemencie zakresu (`tabindex="-1"`, `aria-label="Fragment JSON: <ścieżka>"`). Podświetlenie trwa do pokazania innej ścieżki albo opuszczenia zakładki.

### Widok raportu: `features/result/report-view.ts`

Sekcje z nagłówkami h2 (`text-section-title`), puste listy pokazują „Brak”:

1. **Ostrzeżenia (N):** dla każdego kod (`font-mono`), komunikat i, gdy ścieżka istnieje w JSON-ie, przycisk „Pokaż w JSON” (`aria-label="Pokaż w JSON: <kod>"`). Ścieżka, której nie ma w JSON-ie, jest wypisana tekstem `text-fg-muted` z dopiskiem „(miejsce w szkicu, nie w wyniku)”.
2. **Poprawki autonaprawy (N):** ten sam układ.
3. **Propozycje słowników (N):** nazwa (`font-mono`), tytuł, liczba pozycji, „Używa: <techName, …>”.
4. **Statystyki:** strony, sekcje, pola, stany (lista `dl`).
5. **Przetwarzanie** (`dl`):
   - plik (nazwa, liczba stron, „odszyfrowany” gdy `decrypted`),
   - metoda ekstrakcji (mapa: `pdf_text` → „tekst z PDF”, `ocr` → „OCR”, `docx` → „DOCX”, `xlsx` → „XLSX”, inna → wartość surowa),
   - średnia pewność OCR w % (gdy jest),
   - model LLM, a przy `fallback` lub `ruleBasedDraft` informacja „szkic regułowy (bez LLM)” z powodem,
   - czasy: łączny (`durationMs`) i etapów z `timings` w sekundach z jedną cyfrą po przecinku (`25,1 s`). Etykiety: `normalizeMs` „normalizacja”, `extractMs` „ekstrakcja”, `analyzeMs` „analiza”, `buildMs` „budowa”; inne klucze bez sufiksu `Ms`.

Brak raportu (`report = null` albo nie obiekt): panel pokazuje „Raport niedostępny dla tego wyniku.”

### Komunikacja między widokami

`ResultPage` trzyma `activeTab` i `highlightPath` (sygnały). `report-view` emituje `showInJson(path)` (output), `ResultPage` ustawia oba i obsługuje przewinięcie i fokus po renderze.

## Testy

- `json-lines.spec.ts`: identyczność z `JSON.stringify(…, null, 2)` na mocku „Nadpłata”. Zakresy dla `tabs[0]`, `tabs[0].questions[1]`, `tabs[0].questions[1].field.repeatingSectionGrid[0]`, `title`. Brak klucza dla nieistniejącej ścieżki. Puste obiekty i tablice (`{}`, `[]` w jednej linii).
- `report.spec.ts`: `asReport` dla obiektu, `null`, tablicy, stringa, pól złego typu.
- Efekty/reducer: `report` trafia do wiersza. HTTP: `report=true` w zapytaniu, rozpakowanie `{form, report}` i odpowiedź bez `form`.
- `result-page`: zakładki (strzałki, Home/End, `aria-selected`), domyślna zakładka, „Pokaż w JSON” przełącza zakładkę i fokusuje podświetlony fragment, podgląd zachowuje odpowiedź po przejściu Raport → Podgląd.
- Storybook `Ekrany/Wynik`: warianty z raportem, bez raportu, wynik nie-formularz. Testy a11y przechodzą.

## Zostawione builderowi

- Dokładne klasy Tailwind i odstępy (zgodnie z istniejącymi kartami).
- Czy formatter liczy linie rekurencyjnie, czy przez tokenizację (byle wynik był identyczny ze `stringify`).

## Doprecyzowania po przeglądzie buildera (moje decyzje)

1. **Kiedy link.** „Pokaż w JSON” pojawia się tylko wtedy, gdy spełnione są trzy warunki:
   - ścieżka zaczyna się od `tabs[` (przestrzeń wynikowego JSON-a),
   - ścieżka istnieje dokładnie w `ranges`,
   - kod nie oznacza usunięcia elementu: `R03_EMPTY_PAGE` nigdy nie dostaje linku.

   Dotyczy to ostrzeżeń i poprawek. Ścieżki szkicu (`subject_pages…`, `chunk…`, `title`, `authority_name`, `attachments…`) są wypisywane tekstem z dopiskiem „(miejsce w szkicu, nie w wyniku)”. Dzięki temu ostrzeżenie o `title` ze szkicu nie linkuje do tytułu formularza. Pozostałe ścieżki spoza `tabs[`, których nie ma w JSON-ie, dostają dopisek „(element nie występuje w wyniku)”.
2. **Znane ograniczenie.** Backend zapisuje ścieżkę poprawki w chwili jej wykonania. Późniejsza poprawka strukturalna (opakowanie pola w sekcję, usunięcie pustej strony) może przesunąć indeksy, więc link może wskazać sąsiedni fragment. Akceptujemy to w podglądzie. Właściwa naprawa to ścieżki stanu końcowego po stronie backendu (zgłoszenie do zespołu backendu, poza zakresem).
3. **Słowniki.** `usedBy` to lista `techName` pól (jak w spec §6.2), a liczba pozycji to `items.length`. Pole `description` pokazujemy pod tytułem, gdy jest. `itemStructure` pomijamy.
4. **Trwałość.** Kolejka nie jest zapisywana (do `sessionStorage` trafia tylko slice `auth`), więc raport żyje tyle co wynik. Nie trzeba migracji starych wierszy.
5. **Typ klienta.** Wygenerowana funkcja zwraca `{ [key: string]: any }`. Rozpakowanie `{form, report}` robi `convert-file.http.ts` z kontrolą `'form' in body` i bez rzutowań na typ formularza.
6. **Wynik niebędący formularzem.** Zakładka Podgląd jest ukryta, domyślna jest JSON, a Raport pozostaje dostępny.
