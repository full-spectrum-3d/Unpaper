# Renderer formularza – szkielet

Data: 2026-11-21 · Rozmiar: projekt (pełny design)

## Intencja
Pokazać wynik konwersji tak, jak zobaczy go obywatel w docelowej e-usłudze: klikalny formularz ze stronami, sekcjami i polami ułożonymi według JSON-a w formacie importu Generatora Formularzy COI. To najbardziej przekonujący element dla jury („tak będzie wyglądać e-usługa”). Spec §9.3 (renderer), §9.1 (ekran wyniku), format: `wymagania/OpisImportowanegoPlikuJSON.md`, `wymagania/importowanyPlikJsonSchemat.json`, wygląd docelowy: zrzuty `wymagania/obrazy/nadplata/*.png` i `wymagania/obrazy/numer-porzadkowy/*.png`.

Ten krok to **szkielet**: struktura, nawigacja, wszystkie typy pól i lokalny stan odpowiedzi. Warunki `jsonata`, walidatory z blokadą „Dalej”, słowniki, podpowiedzi i oznaczenie „dane z rejestru” to następny krok.

## Cele
- Na `/result/:id` przełącznik „Podgląd formularza / JSON” (domyślnie podgląd); „Pobierz .json” bez zmian.
- Renderer w motywie `preview` (tokeny z `data-theme="preview"`) odwzorowujący zrzuty: tytuł formularza (`h1`), sekcje jako białe karty z tytułem (`h2`), etykiety nad polami, pola tylko do odczytu na szarym tle, nawigacja „Przerwij wypełnianie” (lewo) i „Wstecz” / „Dalej” (prawo).
- Kolejność stron według `flow.links`, wskaźnik „Krok N z M: <tytuł strony>”, fokus na nagłówku strony po przejściu.
- Wszystkie typy pól z formatu: `SECTION`, `TEXT_FIELD`, `NUMBER`, `TEXTAREA`, `RADIO`, `SELECT`, `CHECKBOX`, `DATEPICKER`, `FILE_UPLOADER`, `TEXT_BLOCK`, `CONSENT_SECTION`; nieznany typ jako czytelny zastępnik.
- Siatka CSS wg `grid-area: {y+1} / {x+1} / span {rows} / span {cols}`.
- Odpowiedzi w lokalnym stanie renderera (signals), zachowane przy przechodzeniu między stronami; funkcja budująca kopię JSON-a z `__userAnswer` (pod `jsonata` w następnym kroku).

## Poza zakresem
- Ewaluacja `states` (`jsonata`: SHOW/HIDE/READ_ONLY…) – w szkielecie wszystkie elementy widoczne.
- Walidatory (`validation`: REQUIRED, PESEL, NIP, REGON, ZIP_CODE, EMAIL, EPUAP, ADE, SERIAL_NUMBER_ID_CARD) i blokada „Dalej”.
- Słowniki (`dictionaryName`) – tylko zastępnik.
- `tooltipMessage`, oznaczenie „dane z rejestru” (`defaultValueType: EXTERNAL_SYSTEM`), sekcje powtarzalne (dodawanie kolejnych wystąpień), wysyłanie plików, pełne podsumowanie na stronie `FINISH`.
- Edycja definicji formularza.

## Anty-cele
- Renderowanie surowego HTML-a z JSON-a bez sanitizacji (opisy mają `<html>…`, linki, obrazki base64).
- Przerwanie całego podglądu przez jedno nieznane / uszkodzone pole.
- Odpowiedzi w store NgRx (zmieniają się przy każdym znaku, nie są współdzielone – spec §3.2).
- Przerysowanie całego formularza przy każdym znaku.
- Wygląd odbiegający od zrzutów (jury porównuje z docelową e-usługą).

## Ograniczenia
- Angular 22 (standalone, signals, `inject()`, bez jawnego `OnPush`), Tailwind 4 z tokenami (motyw `preview`), istniejące `shared/ui` (`app-text-field`, `button[appButton]`, `app-card` jeśli pasuje).
- Typy definicji formularza pisane ręcznie w `features/preview/form-definition.ts` na podstawie `importowanyPlikJsonSchemat.json` (wygenerowany klient ich nie ma – backend nie wystawia modelu w OpenAPI); komentarz, że do zastąpienia typami z OpenAPI, gdy backend je wystawi.
- WCAG 2.1 AA: etykiety (`for`/`id`), grupy (`fieldset`/`legend`) dla RADIO/CHECKBOX/CONSENT, opisy przez `aria-describedby`, obsługa klawiatury, fokus przy zmianie strony.
- Teksty po polsku, bez nowych zależności, commity bez `Co-Authored-By`.

## Podejścia
- **A. Drzewo komponentów + płaska mapa odpowiedzi** (wybrane przez użytkownika): `FormRenderer` → `RendererPage` → `RendererGrid` (rekurencyjnie dla sekcji) → `FieldHost` → komponent na typ pola; `AnswersStore` w renderze trzyma `Map<fieldId, WritableSignal<unknown>>`; `withUserAnswers(definition, answers)` buduje kopię JSON-a z `__userAnswer`.
- B. Signal Forms dla całego formularza (schemat generowany z JSON-a) – dużo kodu, warunki `jsonata` słabo pasują do reguł. Odrzucone.
- C. Jeden sygnał z całym JSON-em i `__userAnswer` w miejscu – kopia dużego drzewa przy każdym znaku. Odrzucone.

## Decyzje użytkownika
- Renderer dostępny na ekranie wyniku (`/result/:id`) z przełącznikiem „Podgląd formularza / JSON”, plus story w Storybooku z oboma wzorcowymi formularzami.
- Działanie z playbacku zaakceptowane: „Krok N z M”, „Wstecz” niewidoczne na pierwszej stronie, „Przerwij wypełnianie” wraca na pierwszą stronę i czyści odpowiedzi, strona `FINISH` po ostatniej `MAIN`, typy pól jak niżej, siatka 3-kolumnowa (na wąskim ekranie 1 kolumna), odpowiedzi lokalne zachowane między stronami, nieznany typ jako zastępnik.
- Podejście A.

## Projekt

### Pliki
```
src/app/features/preview/
  form-definition.ts      typy: FormDefinition, FormTab, Question, FormField, FieldOption, FieldState, ConsentSectionConfig, FlowLink
  page-order.ts           orderTabs(definition): FormTab[]  (wg flow.links)
  answers-store.ts        AnswersStore (provider komponentu renderera)
  with-user-answers.ts    withUserAnswers(definition, answers): FormDefinition z __userAnswer
  form-renderer.ts (+html)       wejście: definition; stan: indeks strony
  renderer-page.ts                strona: h2 tytułu strony (sr/visible), RendererGrid
  renderer-grid.ts                siatka pytań (rekurencja dla SECTION)
  field-host.ts                   @switch po field.type
  fields/  section-field, text-field-field (TEXT_FIELD/NUMBER), textarea-field, radio-field,
           select-field, checkbox-field, date-field, file-uploader-field, text-block-field,
           consent-section-field, unknown-field
  form-renderer.stories.ts        oba wzorcowe formularze (mock-forms z features/import)
src/app/features/result/  result-page (przełącznik Podgląd / JSON)
```

### Model
- Typy zgodne z formatem: `FormDefinition { title: string; tabs: FormTab[]; flow: { links: FlowLink[] } }`, `FormTab { id; title; type: 'MAIN' | 'FINISH'; questions: Question[] }`, `Question { x; y; rows; cols; field: FormField }`, `FormField { id; type: string; techName; title; description?; options?: FieldOption[]; validation?: string[]; dictionaryName?; readOnly?; repeatingSectionGrid?: Question[]; defaultValue?; defaultValueType?; consentSectionConfig?; states?: FieldState[]; questionOrder?; tooltipMessage? }`. `type` jako `string` (nieznane typy muszą przejść), stałe znanych typów jako unia pomocnicza.
- Wejście renderera to `unknown` z wyniku konwersji: lekka weryfikacja kształtu (`isFormDefinition`: `title` string, `tabs` tablica obiektów z `questions` tablicą). Nie pasuje → komunikat „Nie można wyświetlić podglądu: wynik nie ma struktury formularza.” i przełącznik zostaje na JSON.

### Kolejność stron (`orderTabs`)
Start: pierwsza strona `MAIN`, do której nie prowadzi żaden link (gdy brak – pierwsza `MAIN` w tablicy). Dalej po `source → target`. Strony nieosiągnięte przez linki dołączane na końcu w kolejności tablicy, `FINISH` zawsze na końcu. Cykle przerywane (odwiedzona strona nie jest dodawana drugi raz). „Krok N z M” liczy tylko strony `MAIN`; na `FINISH` napis „Podsumowanie”.

### Odpowiedzi (`AnswersStore`)
- `answer(fieldId): WritableSignal<unknown>` – tworzony leniwie; wartość początkowa: `defaultValue` (jeśli jest) przekształcone wg typu (CHECKBOX/CONSENT → tablica nazw, NUMBER → string jak w polu, reszta → string), inaczej `''` / `[]`.
- `reset()` – czyści wszystkie sygnały do wartości początkowych („Przerwij wypełnianie”).
- Konwencja wartości (pod zapytania `jsonata`, które porównują nazwy opcji): RADIO/SELECT → `option.name` (string); CHECKBOX → `string[]` nazw; CONSENT_SECTION → `boolean[]` po indeksie zgody; FILE_UPLOADER → `string[]` nazw wybranych plików (bez wysyłki); DATEPICKER → `YYYY-MM-DD`.
- `withUserAnswers(definition, store)`: głęboka kopia z `field.__userAnswer` = bieżąca wartość dla każdego pola, dla którego istnieje sygnał (pola nietknięte – `defaultValue` lub brak klucza). Czysta funkcja, testowana.

### Pola (komponenty; każde dostaje `field: FormField` i sygnał odpowiedzi)
- `SECTION`: karta (`bg-surface rounded-card p-section`) z `h2` `title`, opis (sanityzowany HTML, gdy niepusty), wewnątrz `RendererGrid` z `repeatingSectionGrid`.
- `TEXT_FIELD` / `NUMBER`: `app-text-field` (`label` = `title`, `description` = opis tekstowy, `[(value)]`), `readOnly` → atrybut `readonly` i tło `bg-surface-readonly` (rozszerzyć `app-text-field` o wejście `readonly`, jeśli brak); `NUMBER` → `inputmode="decimal"`.
- `TEXTAREA`: etykieta, `<textarea>` z licznikiem „N/8000” (stała 8000 jak na zrzucie 13), `aria-describedby` licznika.
- `RADIO`: `fieldset` + `legend` (`title`), pionowa lista radio (`name` = `field.id`), etykiety z `option.name`.
- `SELECT`: etykieta + natywny `<select>` z pustą opcją „Wybierz”; opcje z `options`; gdy `dictionaryName` i brak opcji → jedna wyłączona opcja „Słownik: <dictionaryName>” (zastępnik do następnego kroku).
- `CHECKBOX`: `fieldset` + `legend`, lista checkboxów; bez opcji → pojedynczy checkbox z etykietą `title`.
- `DATEPICKER`: etykieta + `<input type="date">`.
- `FILE_UPLOADER`: etykieta, ramka z przyciskiem „Dodaj lub przeciągnij plik” (otwiera `input type=file`, zapisuje nazwy), tabelka „Dopuszczalny format pliku / Maksymalny rozmiar pliku / Maksymalna liczba plików” z wartościami stałymi jak na zrzucie 13 (`.jpg, .pdf, .png, .jpeg, .doc, .odt, .docx, .ods`, `10 MB`, `1`) – shortcut do czasu, gdy format JSON będzie niósł te ograniczenia; lista wybranych nazw.
- `TEXT_BLOCK`: sanityzowany HTML z `description` (albo `title`, gdy opis pusty).
- `CONSENT_SECTION`: `fieldset`, `legend` = `title`; dla każdej zgody checkbox z etykietą = sanityzowany HTML `description`, gwiazdka/„(wymagana)” przy `required: true`.
- Nieznany typ: ramka `border-dashed` z tekstem „Nieobsługiwany typ pola: <type>” i tytułem pola.
- Opisy HTML: `[innerHTML]` (sanitizer Angulara usuwa skrypty i niebezpieczne atrybuty); puste `<html><head></head><body></body></html>` traktowane jak brak opisu (helper `hasText(html)`).

### Nawigacja i strona
- Nagłówek formularza `h1` = `definition.title`; pod nim „Krok N z M: <tytuł strony>” jako `h2` strony z `tabindex="-1"` – fokus po zmianie strony (`afterNextRender`), przewinięcie do góry.
- Przyciski: „Przerwij wypełnianie” (`button` stylizowany jak link, lewo) → `store.reset()` i strona 1; „Wstecz” (`secondary`, ukryty na pierwszej stronie); „Dalej” (`primary`, na ostatniej `MAIN` prowadzi do `FINISH`; na `FINISH` ukryty).
- Siatka: `grid grid-cols-3 gap-…`, element `style.grid-area`; poniżej breakpointu `sm` wszystkie elementy w jednej kolumnie (`grid-area` nadpisane na auto) – zrzuty i tak mają pełną szerokość.

### Ekran wyniku
- Przełącznik dwóch przycisków (`role="tablist"`/`tab` albo grupa przełączników z `aria-pressed` – wybór wykonawcy, byle dostępny) „Podgląd formularza” / „JSON”; domyślnie podgląd, gdy `isFormDefinition(result)`, inaczej JSON z komunikatem.
- Renderer opakowany w kontener `data-theme="preview"` z tłem `bg-bg` (jak zrzuty).

## Testy
- Unit: `orderTabs` (liniowe linki, start bez linku przychodzącego, brak linków, nieosiągnięte strony, cykl, FINISH na końcu), `isFormDefinition` (poprawny wzorzec, `null`, brak `tabs`, `tabs` nie-tablica), `AnswersStore` (wartości początkowe wg typu i `defaultValue`, `reset`), `withUserAnswers` (wstawia `__userAnswer`, nie mutuje wejścia, zagnieżdżone sekcje), `hasText` (pusty szkielet HTML → false).
- Storybook (`Ekrany/Podgląd formularza`): oba wzorcowe formularze – pierwsza strona: `h1` tytułu, sekcja „Urząd, do którego jest składany wniosek” z polem tylko do odczytu „Urząd Gminy Ulan-Majorat”; RADIO w `fieldset` z legendą; „Dalej” → „Krok 2 z 3” i fokus na nagłówku strony; „Wstecz” wraca, wpisana wartość zachowana; „Przerwij wypełnianie” czyści wartość i wraca na krok 1; ostatnia strona → „Podsumowanie”; story z nieznanym typem pola → zastępnik; a11y w motywie `preview`.
- Story ekranu wyniku: przełącznik Podgląd/JSON, wynik bez struktury formularza → komunikat i JSON.

## Rozstrzygnięcia po przeglądzie wykonawcy (decyzje autora designu)
1. **Dane z rejestru (`defaultValueType: EXTERNAL_SYSTEM`):** `defaultValue` to ścieżka w rejestrze (np. `PESEL.name`, `MLPZ.street`), nie wartość. Szkielet pokazuje przykładową wartość testową z małej tabeli w `features/preview/sample-registry-data.ts` (np. `PESEL.name` → „JAN”, `PESEL.surname` → „KOWALSKI”, `PESEL.pesel` → „51051101608”, ulice/miasta z `MLPZ.*`), zgodnie ze spec §9.3 („przykładowe wartości testowe”); nieznana ścieżka → puste pole. Oznaczenie „dane z rejestru” – następny krok.
2. **Typy wartości pod `jsonata`:** SELECT/RADIO trzymają `string` (nazwa opcji); gdy `defaultValue` jest tablicą (np. `["Polska"]`), bierzemy pierwszy element. `jsonata` traktuje skalar w `in` jak tablicę jednoelementową, więc zapytania typu `"Polska" in …__userAnswer` działają.
3. **Kształt wyniku:** wynik konwersji to sama definicja formularza (bez opakowania; `/forms/convert` bez `report=true`). Klucz odpowiedzi = `field.id`; zakładamy unikalność (generuje je backend). `isFormDefinition` odrzuca inne kształty komunikatem.
4. **Osadzenie i nagłówki:** renderer poza `app-card` strony wyniku, na pełną szerokość, w kontenerze `data-theme="preview"` z tłem `bg-bg`. Strona ma już `h1` (nazwa pliku), więc tytuł formularza to `h2` (wizualnie jak `text-title` motywu preview), „Krok N z M: …” to `h3` (cel fokusu), tytuły sekcji `h4`.
5. **Siatka:** `grid-auto-rows: auto` (wartości `rows` tylko w `grid-area`, bez stałej wysokości wiersza). Kolejność w DOM (i na wąskim ekranie) według `y`, potem `x` – nie według kolejności w tablicy ani `questionOrder`.
6. **Commity:** bez linii `Co-Authored-By` (reguła użytkownika).

## Decyzja użytkownika po przeglądzie: warunki SHOW/HIDE w szkielecie
Bez warunków pierwsza strona wzorca „nadpłata” pokazuje 12 sekcji zamiast 4 ze zrzutu, więc do szkieletu wchodzi podstawowa ewaluacja `states` (zmienia sekcję „Poza zakresem”: SHOW/HIDE są w zakresie, pozostałe typy – np. READ_ONLY – nadal w następnym kroku).
- Biblioteka `jsonata@^2.2.2` (MIT, oficjalna implementacja JS) – jedyna nowa zależność; ląduje w leniwym chunku strony wyniku (trasa `result/:id` jest już ładowana leniwie).
- `features/preview/visibility.ts`: `evaluateVisibility(definition: FormDefinition, answers): Promise<ReadonlySet<string>>` – zwraca zbiór `field.id` ukrytych pól. Wejście `jsonata` to `withUserAnswers(definition, answers)`.
- Reguła: pole jest widoczne, gdy (nie ma stanów SHOW **albo** którekolwiek zapytanie SHOW zwraca prawdę) **i** żadne zapytanie HIDE nie zwraca prawdy. Prawda = wynik truthy (`true`, niepusta tablica z `true`). Błąd kompilacji lub ewaluacji zapytania → pole widoczne (fail-open) + `console.warn` z `techName`; wyrażenia kompilowane raz (cache po tekście zapytania).
- Ukrycie sekcji ukrywa całą jej zawartość. Ukryte pola zachowują wpisane odpowiedzi (wracają po ponownym pokazaniu).
- Przeliczanie po każdej zmianie odpowiedzi (sygnał wersji w `AnswersStore`), z debounce do następnego mikrozadania; do czasu pierwszego wyniku pola ze stanami SHOW są ukryte (unikamy mignięcia 12 sekcji), pola bez stanów widoczne od razu.
- Testy: `evaluateVisibility` na wzorcu „nadpłata” – domyślnie (radio „Swoim” z `defaultValue`, jeśli jest, inaczej brak odpowiedzi) widoczne tylko sekcje ze zrzutu 01; po ustawieniu odpowiedzi „Innej osoby” w `wybierz_w_czyim_imieniu_wnioskujesz` widoczne „Dane innej osoby”, „Adres zamieszkania innej osoby”, „Pełnomocnictwo”, „Opłata skarbowa”; zapytanie z błędem składni → pole widoczne; HIDE z prawdą → ukryte. Story: kliknięcie „Innej osoby” pokazuje sekcję „Dane innej osoby”.

## Zostawione wykonawcy
- Dokładne klasy Tailwind w granicach zrzutów (odstępy, rozmiary nagłówków z tokenów `preview`).
- Wybór między rozszerzeniem `app-text-field` o `readonly` a osobnym polem tylko do odczytu.
- Forma przełącznika Podgląd/JSON (tabs vs `aria-pressed`).
- Czy `RendererPage` jest osobnym komponentem, czy częścią `FormRenderer`.
