# Normalizacja (krok [2]) – projekt

| | |
|---|---|
| Data | 2026-11-21 |
| Zakres | `backend/app/pipeline/normalize.py`, `api/v1/health.py` (`/ready`), `main.py` (wykrycie konwertera przy starcie), `pyproject.toml` (znacznik `converter`) |
| Podstawa | specyfikacja §3.4, §5.2, §6.3–6.4, §10.2–10.3, §11, §12 |
| Poza zakresem | ekstraktory `extract/*`, podpięcie pod `POST /forms/convert`, semafor `MAX_CONCURRENT_JOBS` (obejmuje całe zadanie, nie tylko konwersję), frontend |

## 1. Cel

Ekstraktory obsługują DOCX i XLSX, a nie stare formaty. Krok [2] zamienia DOC na DOCX i ODS na XLSX przez niezmodyfikowane binarium LibreOffice uruchamiane jako osobny proces. Pozostałe formaty przekazuje dalej bez zmian. Bez LibreOffice w obrazie (Plan B ze spec §3.4) DOC i ODS dostają 415, a reszta działa.

## 2. Cele, nie-cele, anty-cele

**Cele**
- Wynik ma tę samą postać dla każdego formatu: strumień i docelowy `FileKind`. Ekstraktor nie musi wiedzieć, czy plik był konwertowany.
- Izolacja na żądanie: osobny katalog roboczy i osobny profil LibreOffice. Dwa równoległe `soffice` się nie blokują.
- Po konwersji na dysku nie zostaje nic, także po błędzie, timeoucie albo anulowaniu żądania (§10.3, M5).
- Testy działają bez LibreOffice (proces jest podstawiany). Test na prawdziwym `soffice` jest opcjonalny.

**Nie-cele**
- Konwersja innych formatów, na przykład PDF→obraz albo DOCX→PDF.
- Utrzymywanie stale działającego procesu LibreOffice (unoserver).
- Nowe zależności Pythona.

**Anty-cele**
- Wywołanie przez powłokę albo argument pochodzący z uploadu (nazwa pliku, rozszerzenie, treść).
- Uruchomienie makr z dokumentu.
- Osierocony `soffice.bin` po timeoucie.
- Treść ani nazwa dokumentu w logach.

## 3. Ograniczenia

- Kontener `api`: `read_only`, zapisywalny jest tylko tmpfs `/tmp` (512 MB), `cap_drop: ALL`, użytkownik `app` bez uprawnień, brak internetu.
- Alpine: `soffice` to skrypt, który uruchamia `oosplash` i dopiero ten uruchamia `soffice.bin`. Zabicie samego dziecka nie wystarcza.
- Lokalnie (Windows) LibreOffice nie jest zainstalowany.
- Tylko biblioteka standardowa: `asyncio`, `tempfile`, `shutil`, `os`, `signal`.

## 4. Rozważone podejścia

| Podejście | Wady / zalety | Decyzja |
|---|---|---|
| **1. `normalize()` konwertuje i od razu wczytuje wynik do `SpooledTemporaryFile`, katalog roboczy jest usuwany w `finally`** | Katalog żyje tylko podczas konwersji, sprzątanie jest w jednym miejscu, ekstraktor zawsze dostaje strumień. Koszt: jedna kopia wyniku (≤ kilkadziesiąt MB) | **wybrane** |
| 2. Kontekst `async with`, który zwraca ścieżkę w katalogu żądania | Bez kopiowania. Sprzątanie zależy od wołającego, a ekstraktory musiałyby obsługiwać i ścieżkę, i strumień | odrzucone |
| 3. Stały proces LibreOffice (unoserver) | Szybsze o start procesu (1–3 s). Nowa zależność i wspólny profil oraz stan dla wszystkich żądań, wbrew §10.2–10.3 | odrzucone |

Brak LibreOffice: **wariant A**. Obecność sprawdzamy raz przy starcie. DOC i ODS dostają `415 UNSUPPORTED_EXTENSION` z wyjaśnieniem w `detail`, a `/health/ready` zwraca `"degraded": ["converter"]`. Kontrakt API nie dostaje nowego kodu błędu.

## 5. Projekt

### 5.1. Interfejs

```python
@dataclass(slots=True)
class NormalizedDocument:
    kind: FileKind          # PDF | DOCX | XLSX | JPEG | PNG – nigdy DOC/ODS
    file: IO[bytes]         # ustawiony na początek
    converted: bool         # True: `file` to nowy strumień, własność NormalizedDocument
    def close(self) -> None # zamyka `file` tylko gdy converted; upload zamyka jego właściciel

async def normalize(
    upload: ValidatedUpload,
    converter: Converter | None,
    limits: UploadLimits,
    *, tmp_dir: str | None = None,
) -> NormalizedDocument
```

- Formaty przepuszczane: `NormalizedDocument(upload.kind, upload.file, converted=False)`, bez kopiowania.
- DOC/ODS przy `converter is None`: `AppError(UNSUPPORTED_EXTENSION, "Format .doc wymaga LibreOffice, który nie jest dostępny w tej instalacji")`.
- `Converter`: klasa `LibreOfficeConverter(soffice_path, timeout_s, runner)`. Fabryka `find_converter(settings)` szuka `soffice` przez `shutil.which` i zwraca `None`, gdy go nie ma. `create_app` przypisuje wynik do `app.state.converter`, tak jak `llm_client` (może go też dostać jako parametr w testach). Zależność FastAPI: `get_converter`.

### 5.2. Przebieg konwersji

1. `tempfile.TemporaryDirectory(prefix="coi-conv-", dir=tmp_dir)` zawiera `in/`, `out/` i `profile/`.
2. `upload.file` jest kopiowany do `in/input.doc` albo `in/input.ods`. Nazwa jest stała, nie pochodzi z uploadu.
3. Profil jest wstępnie zasiany plikiem `profile/user/registrymodifications.xcu`, który wyłącza makra: `Office.Common/Security/Scripting/MacroSecurityLevel = 3` i `DisableMacrosExecution = true`. LibreOffice headless domyślnie i tak nie uruchamia makr przy konwersji, to tylko dodatkowe zabezpieczenie.
4. Stałe argumenty, `shell=False`:
   ```
   soffice -env:UserInstallation=<profile.as_uri()> --headless --invisible --norestore
           --nolockcheck --nodefault --nologo
           --convert-to docx:"MS Word 2007 XML" | xlsx:"Calc MS Excel 2007 XML"
           --outdir <out> <in/input.ext>
   ```
   Środowisko jest minimalne: `PATH`, `HOME=<katalog roboczy>`, `TMPDIR=<katalog roboczy>`, `LANG=C.UTF-8`. Bez tego LibreOffice próbowałby pisać do `$HOME`, a w kontenerze jest on tylko do odczytu.
5. `Runner` (protokół) uruchamia proces. Implementacja produkcyjna używa `asyncio.create_subprocess_exec(..., start_new_session=True, stdin=DEVNULL, stdout=DEVNULL, stderr=PIPE)` i `asyncio.wait_for(timeout=CONVERTER_TIMEOUT_S)`. Po przekroczeniu czasu albo anulowaniu zadania wysyła `os.killpg(pgid, SIGKILL)` do całej grupy, a na systemach bez `killpg` używa `proc.kill()`, i czeka na zakończenie. Z stderr zachowujemy tylko ostatnie ~2 KB, do logu na poziomie DEBUG.
6. Wynik: oczekiwany plik `out/input.docx|xlsx` musi istnieć i być niepusty. `soffice` potrafi zwrócić kod 0 bez wyniku, więc nie wystarczy sprawdzić kodu wyjścia. Plik jest kopiowany do `SpooledTemporaryFile(max_size=limits.spool_max_bytes, dir=tmp_dir)`, a potem sprawdzany tym samym `inspect_zip_document(kind, limits)` co upload (limity ZIP, struktura OOXML, defusedxml).
7. `finally`: katalog roboczy jest usuwany (`TemporaryDirectory.cleanup`), także przy błędzie, timeoucie i `CancelledError`. Przy błędzie spool z wynikiem jest zamykany.

### 5.3. Błędy (RFC 9457, `core/errors.py`)

| Sytuacja | Kod |
|---|---|
| DOC/ODS, brak LibreOffice | 415 `UNSUPPORTED_EXTENSION` |
| Przekroczony `CONVERTER_TIMEOUT_S` | 504 `PROCESSING_TIMEOUT` |
| Kod wyjścia ≠ 0, brak pliku wynikowego, pusty wynik | 422 `DOCUMENT_UNREADABLE` |
| Wynik nie przechodzi `inspect_zip_document` (`UploadError`) | 422 `DOCUMENT_UNREADABLE` (`detail` bez treści pliku) |
| Nie da się uruchomić procesu (`OSError`, np. binarium zniknęło) | 422 `DOCUMENT_UNREADABLE`, log WARNING |

Logi zawierają tylko metadane: rodzaj, rozmiar wejścia i wyjścia, czas, kod wyjścia. Bez nazwy pliku.

### 5.4. `/health/ready`

Gdy `app.state.converter is None`, do listy `degraded` trafia `"converter"`. Status pozostaje `ok`, bo pozostałe formaty działają.

### 5.5. Testy

- **Jednostkowe** (`tests/unit/test_normalize.py`), z atrapą `Runner`:
  - przepuszczanie każdego formatu bez kopiowania,
  - DOC→DOCX i ODS→XLSX: atrapa zapisuje mały poprawny DOCX/XLSX do `--outdir`,
  - sprawdzenie argumentów (stałe, nazwa pliku wygenerowana, profil wewnątrz katalogu roboczego, osobny dla każdego wywołania),
  - zasiany plik `.xcu`,
  - timeout → 504, kod wyjścia ≠ 0 i brak wyniku → 422, wynik będący bombą ZIP lub śmieciem → 422,
  - brak konwertera → 415,
  - katalog roboczy usunięty w każdej z tych ścieżek i przy anulowaniu,
  - dwa równoległe wywołania mają różne profile.
- **Runner produkcyjny** (POSIX, pomijany na Windows): proces potomny, który się zawiesza (`python -c` uruchamiający wnuka i `sleep`) → po timeoucie cała grupa jest zabita.
- **Na żywo**: znacznik `@pytest.mark.converter` („wymaga LibreOffice (soffice)”), domyślnie wyłączony w `addopts`. Test konwertuje `materials/wniosek-1/*.doc` i `*.ods` i porównuje tekst akapitów z oryginałem `.docx` przez python-docx, a wartości komórek z `.xlsx` przez openpyxl. Pomijany, gdy brakuje `materials/` albo `soffice`.
- `/ready`: wpis `degraded` z konwerterem i bez niego.

## 6. Pozostawione wykonawcy

- Dokładna treść `registrymodifications.xcu` i to, czy `--invisible` jest potrzebne obok `--headless`, do sprawdzenia w kontenerze.
- Jeśli porównanie tekstu DOC→DOCX z oryginałem okaże się zbyt surowe (różnice w białych znakach, polach), test na żywo porównuje znormalizowany tekst, nie strukturę.
