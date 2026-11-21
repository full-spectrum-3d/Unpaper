# Ekstrakcja (krok [3]) – projekt

| | |
|---|---|
| Data | 2026-11-21 |
| Zakres | `backend/app/pipeline/extract/*`, nowe kody ostrzeżeń `W11`, `W12`, testy `tests/unit/extract/`, `tests/extraction/` |
| Podstawa | specyfikacja §5.3, §6.2, §10.2–10.3, §12, §13.1, §14 R1; projekt LLM §5.1 (`DocumentModel`) |
| Poza zakresem | podpięcie pod `POST /forms/convert`, tryb wizyjny (`EXTRACTION_VLM_ENABLED`), zmiany `DocumentModel` i `to_prompt_text()` |

## 1. Cel

Zamienić znormalizowany dokument (PDF, DOCX, XLSX, JPEG, PNG – wynik kroku [2]) na `DocumentModel`: strony z blokami w kolejności czytania, z rodzajem bloku (`heading`, `paragraph`, `label`, `input_placeholder`, `checkbox_option`, `table`, `table_cell`). LLM dostaje z tego zwięzły tekst z markerami; jakość szkicu zależy od tego, czy pola i opcje wyboru są rozpoznane.

## 2. Obserwacje z próbek (9 formularzy × do 8 formatów)

| Format | Co widać | Konsekwencja |
|---|---|---|
| PDF | Wszystkie mają warstwę tekstu, ale „stypendium” to 16 stron, z czego 15 to skany (45 słów w całym pliku) | decyzja tekst/OCR **per strona** |
| PDF | Pola to siatki cienkich wypełnionych prostokątów (szer. lub wys. ≈ 0), kratki NIP po ~17 pt; checkboxy to glify Wingdings z prywatnego obszaru Unicode (``) | komórki z linii (pdfplumber `find_tables`), puste komórki → pole; glify → opcja |
| DOCX | „Zwrot opłaty” i „Deklaracja”: cała treść w polach tekstowych z pozycją absolutną (130 i 1302 `w:txbxContent`, każde zdublowane w `mc:Fallback`) | czytamy tylko `mc:Choice`, kolejność z pozycji kotwicy |
| DOCX | Checkboxy jako punktor listy z czcionką Symbol/Wingdings (`lvlText=""`) albo znak `□` w tekście | punktor z `numbering.xml` → opcja |
| XLSX | Etykieta w scalonej komórce, obok pusta komórka z obramowaniem (pole); kratki NIP jako ciąg pojedynczych komórek | geometria z szerokości kolumn i wysokości wierszy |
| JPG/PNG | Strony A4 przy 200 DPI sklejone w jeden długi obraz (1654×4678 = 2 strony, 1654×37424 = 16 stron); „nadpłata” w skali szarości 130 DPI | podział obrazu na strony według proporcji A4 |

## 3. Rozważone podejścia

| Podejście | Ocena | Decyzja |
|---|---|---|
| **1. Wspólny silnik układu: każdy format daje elementy z geometrią (fragmenty tekstu, puste ramki, tabele), a jeden moduł składa z nich linie i bloki** | jedna implementacja heurystyk (etykieta przed polem, checkbox obok tekstu, nagłówek po rozmiarze/pogrubieniu) dla PDF, OCR, pól tekstowych DOCX i XLSX; testowalny bez plików | **wybrane** |
| 2. Osobne heurystyki w każdym ekstraktorze | prościej na start, ale cztery kopie tych samych reguł o różnej jakości | odrzucone |
| 3. Tylko tekst (bez geometrii), pola zostawić LLM-owi | LLM nie widzi pustych ramek ani kratek – w „zwrocie opłaty” i „deklaracji” zniknęłyby wszystkie pola | odrzucone |

Zwykłe akapity i tabele DOCX nie mają geometrii – idą bezpośrednio do bloków, ale korzystają z tych samych reguł tekstowych (`text_rules`).

## 4. Projekt

### 4.1. Pliki

```
pipeline/extract/
  __init__.py      # extract(doc, settings, *, ocr=None, deadline=None) -> ExtractionResult
  builder.py       # DocumentBuilder: kolejne id b1…, strony, bloki → DocumentModel
  text_rules.py    # glify checkboxów, wykropkowania, reguły nagłówka/etykiety
  layout.py        # Span / Frame / TableGrid → linie → bloki (format-agnostyczne)
  pdf.py           # pdfplumber: słowa, ramki z linii, tabele, AcroForm; skan → OCR
  docx.py          # python-docx: akapity, tabele, listy, pola tekstowe, page breaki
  xlsx.py          # openpyxl: komórki, scalenia, obramowania → geometria
  image.py         # preprocessing, podział na strony, OcrEngine, TesseractOcr
```

### 4.2. Interfejs

```python
@dataclass(slots=True)
class ExtractionResult:
    document: DocumentModel
    warnings: list[ConversionWarning]

def extract(doc: NormalizedDocument, settings: Settings, *,
            ocr: OcrEngine | None = None, deadline: float | None = None,
            clock: Callable[[], float] = time.monotonic) -> ExtractionResult
```

- Synchroniczna (CPU, pdfminer, Tesseract): wywołujący uruchamia ją w wątku, jak `normalize`.
- `ocr=None` → `TesseractOcr(settings.ocr_lang)`; testy podstawiają atrapę.
- `deadline` sprawdzany między stronami → `AppError(PROCESSING_TIMEOUT)`.
- Uszkodzony plik mimo walidacji → `AppError(DOCUMENT_UNREADABLE)`; tekst wyjątku biblioteki nie trafia do odpowiedzi.
- `source.method`: `pdf_text` / `docx` / `xlsx`; `ocr` dla obrazów i dla PDF, w którym choć jedna strona przeszła przez OCR.

### 4.3. Silnik układu (`layout.py`)

Wejście jednej strony: `Span(text, bbox, confidence, bold, size)`, `Frame(bbox)` (pusta ramka) i `TableGrid(bbox, cells)`; współrzędne w punktach, `y` rośnie w dół.

1. Ramki: odrzucamy te, w których leży środek jakiegoś fragmentu tekstu (to obramowanie etykiety, nie pole). Ramki stykające się poziomo w tej samej linii albo pionowo o tych samych krawędziach łączymy (kratki NIP, wielowierszowe pole uzasadnienia → jedno pole). Ramka kwadratowa 5–20 pt to checkbox.
2. Linie: elementy sortujemy po górnej krawędzi; element dołącza do linii, gdy pokrywa się z nią pionowo w ≥ 50% mniejszej wysokości. Tabela zawsze tworzy własną linię.
3. Segmenty: w linii od lewej; nowy segment przy przerwie > 2× wysokość linii oraz na każdej ramce (dwie kolumny „Wnioskodawca … Adresat” to dwa bloki).
4. Klasyfikacja segmentu: checkbox (ramka albo glif na początku; kilka glifów w jednym segmencie → kilka opcji) → `checkbox_option`; pole → `input_placeholder`; tekst bezpośrednio przed polem albo kończący się `:` → `label`; nagłówek (§4.4) → `heading`; reszta → `paragraph`. Sam wykropkowany ciąg → `input_placeholder`.
5. Łączenie zawiniętych akapitów: kolejna linia `paragraph` dokleja się do poprzedniej, gdy odstęp < 0,8× wysokość linii, poprzednia sięga ≥ 85% szerokości tekstu strony, a żadna nie ma wykropkowania ani nie kończy się `:`.

`confidence` bloku = średnia z fragmentów (tylko OCR).

### 4.4. Reguły tekstowe (`text_rules.py`)

- Glify checkboxów: `☐ □ ■ ▢ ◻ ❑ ❒ ☑ ☒` oraz znaki Wingdings/Symbol z obszaru prywatnego `         `.
- Wykropkowanie: `[.…_]{3,}` (ten sam wzorzec co w `DocumentModel`).
- Nagłówek: rozmiar ≥ 1,15× mediana rozmiaru tekstu strony; albo cały segment pogrubiony i jedyny w linii; albo ≥ 80% wielkich liter przy ≥ 6 literach. Zawsze ≤ 150 znaków, bez wykropkowania, bez glifu checkboxa, nie zaczyna się od małej litery.
- DOCX: styl `Heading*`/`Nagłówek*`/`Title`/`Tytuł` albo `outlineLvl` → nagłówek bez dalszych warunków.

### 4.5. Formaty

**PDF** (`pdf.py`): strona „tekstowa”, gdy ma ≥ 20 znaków niebiałych; inaczej rasteryzacja pypdfium2 pod `PDFIUM_LOCK` w `OCR_DPI` (skala obniżana tak, by obraz miał ≤ `MAX_IMAGE_PIXELS`) i OCR jak dla obrazu. Słowa z `extract_words(extra_attrs=["fontname","size"])`, pogrubienie po nazwie czcionki (`Bold`, `Black`, `Heavy`). Komórki z `find_tables` (strategia linii): tabela z ≥ 2 komórkami z tekstem i ≥ 2 wierszami/kolumnami → `TableGrid` (słowa z jej obszaru nie są już fragmentami); puste komórki pozostałych → `Frame`. Pola AcroForm (`Widget`, `Tx`/`Btn`) → `Frame`.

**DOCX** (`docx.py`): elementy `w:body` po kolei (także zawartość `w:sdt`). Strony dzielą `w:br w:type="page"`, `pageBreakBefore` i sekcje z `sectPr` w akapicie. Tabela → `table` + `table_cell` (komórki scalone raz, tekst zagnieżdżonych tabel doklejony). Punktor listy z glifem checkboxa albo pole `w:checkBox`/`w14:checkbox` → `checkbox_option`; pole `FORMTEXT` → doklejony `[POLE]` (wykropkowanie). Pola tekstowe: tylko `mc:Choice` i `w:pict` poza `mc:Fallback`; pozycja kotwicy (`posOffset`, EMU → pt) daje `Span`, puste kształty kwadratowe 5–20 pt → `Frame`; całość przez silnik układu, wstawiona za akapitem kotwiczącym.

**XLSX** (`xlsx.py`): każdy widoczny arkusz = strona; ukryte wiersze i kolumny pomijane; `data_only=True` (wartości formuł). Geometria: szerokość kolumny × 5,6 pt (domyślnie 8,43), wysokość wiersza w pt (domyślnie 15). Komórka (albo zakres scalony) z wartością → `Span` (pogrubienie i rozmiar z czcionki); pusta komórka obramowana z ≥ 3 stron → `Frame`. Arkusz bez treści jest pomijany; skoroszyt bez treści → jedna pusta strona.

**JPEG/PNG** (`image.py`): `ImageOps.exif_transpose`, skala szarości, autokontrast; obraz wyższy niż 1,6× szerokość dzielimy na `round(h / (w·√2))` stron (≤ `MAX_PDF_PAGES`). Orientacja z Tesseract OSD (błąd OSD = brak obrotu). `TesseractOcr.recognize(image) -> list[OcrWord]` z `image_to_data` (`--psm 3`), słowa z `conf < 0` pomijane, `conf/100` → `confidence`. Piksele → punkty: `72 / DPI` (DPI z metadanych, domyślnie 200).

### 4.6. Ostrzeżenia

| Kod | Kiedy |
|---|---|
| `W11_OCR_UNAVAILABLE` | strona wymaga OCR, a Tesseract nie jest zainstalowany albo zawiódł. Strona zostaje pusta, pipeline idzie dalej (LLM dostaje mniej tekstu albo fallback `empty_document`) |
| `W12_LOW_OCR_CONFIDENCE` | średnia pewność OCR strony < 0,6; komunikat podaje numery stron |

### 4.7. Bezpieczeństwo i zasoby

- Dane nie trafiają na dysk poza strumieniem z kroku [2]; OCR dostaje obraz w pamięci (pytesseract tworzy pliki tymczasowe w `TMPDIR`, czyli w tmpfs, i je usuwa).
- XML: python-docx parsuje z `resolve_entities=False`, openpyxl używa `defusedxml`; DTD i bomby ZIP odrzuca już walidacja.
- Rasteryzacja ma limit pikseli; Tesseract ma timeout na stronę (`OCR_PAGE_TIMEOUT_S = 60`).
- Logi: tylko liczby (strony, bloki, czas, metoda), bez treści.

## 5. Testy

- `tests/unit/extract/`: silnik układu na ręcznie zbudowanych fragmentach; DOCX i XLSX budowane w pamięci (python-docx, openpyxl, surowy XML pól tekstowych); PDF generowany w teście jako minimalny plik (Helvetica, operatory `re`/`Tj`); OCR przez atrapę `OcrEngine`.
- `tests/extraction/test_materials.py`: spec §13.1 – dla każdego pliku z `COI_MATERIALS_DIR` (pomijany bez zmiennej) `DocumentModel` zawiera kluczowe frazy formularza; obrazy i skany tylko ze znacznikiem `ocr` (domyślnie pomijany, wymaga Tesseracta).

## 6. Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Heurystyki nagłówków na nieznanych blankietach | progi w jednym module, test na wszystkich 9 formularzach; błędny `heading` zmienia tylko marker w prompcie |
| Kolejność czytania w układach dwukolumnowych | segmenty w linii od lewej – kolumny przeplatają się wierszami, ale etykieta zostaje przy swoim polu |
| OCR długich obrazów na CPU (16 stron) | `deadline` między stronami, limit stron, tryb wizyjny jako przyszłe rozszerzenie |
| Brak Tesseracta poza Dockerem | `W11` zamiast błędu; test na żywo za znacznikiem `ocr` |
