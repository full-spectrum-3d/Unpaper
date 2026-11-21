# Normalizacja (krok [2]) – plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DOC→DOCX i ODS→XLSX przez LibreOffice headless, w izolowanym katalogu z timeoutem. Pozostałe formaty przechodzą bez zmian, a przy braku `soffice` DOC/ODS dostają 415.

**Architecture:** Kod jest podzielony na dwa moduły. `pipeline/converter.py` uruchamia proces (podstawiany `Runner`), buduje argumenty LibreOffice, zasiewa profil i wykrywa `soffice`. `pipeline/normalize.py` zarządza katalogiem tymczasowym, kopiuje wynik do `SpooledTemporaryFile`, ponownie kontroluje ZIP i mapuje błędy na `AppError`. `create_app` wykrywa konwerter przy starcie, a `/ready` zgłasza jego brak w `degraded`.

**Tech Stack:** Python 3.14, asyncio subprocess, tempfile, FastAPI, pytest + pytest-asyncio, python-docx/openpyxl (tylko w testach do budowy plików).

**Spec:** `docs/superpowers/specs/2026-11-21-normalize-design.md`

## Global Constraints

- Bez nowych zależności Pythona. Tylko biblioteka standardowa i to, co już jest w `pyproject.toml`.
- `shell=False`. Argumenty są stałe, a plik wejściowy nazywa się zawsze `input.doc` albo `input.ods`, nigdy nazwą z uploadu.
- Profil LibreOffice i katalog wyjściowy są osobne dla każdego wywołania i leżą wewnątrz katalogu roboczego `TemporaryDirectory(prefix="coi-conv-", dir=tmp_dir)`.
- Timeout: `Settings.converter_timeout_s` (domyślnie 60). Po przekroczeniu ubijamy całą grupę procesów (`os.killpg(..., SIGKILL)`), a na systemach bez `killpg` sam proces (`proc.kill()`).
- Błędy: timeout → `ErrorCode.PROCESSING_TIMEOUT`, nieudana konwersja albo wynik nieprzechodzący kontroli → `ErrorCode.DOCUMENT_UNREADABLE`, brak konwertera → `ErrorCode.UNSUPPORTED_EXTENSION`.
- Logi zawierają tylko metadane (rodzaj, rozmiary, czas, kod wyjścia). Bez nazwy i treści pliku.
- Komentarze i docstringi po polsku, jak w reszcie `backend/app`.
- Komendy uruchamiamy z `backend/`: `uv run pytest`, `uv run mypy app`, `uv run ruff check app tests`. Wszystkie trzy muszą przejść po każdym zadaniu.
- Commity: jedna linia, conventional commits, bez `Co-Authored-By`.
- Nie dotykamy `frontend/`.

## Review Focus

1. Klient zrywa połączenie w trakcie konwersji (anulowanie zadania). Oczekiwane: grupa procesów `soffice` jest zabita, a katalog roboczy usunięty. Testy: Task 1 `test_run_process_cancel_kills_process`, Task 3 `test_cancel_cleans_up`.
2. Pozycja `upload.file` po normalizacji. Ekstraktor albo ponowna próba czyta od początku, więc strumień ma być na pozycji 0 w obu ścieżkach. Test: Task 3 `test_upload_stream_rewound`.
3. `soffice` kończy się kodem 0, ale zapisuje wynik pod inną nazwą albo nie zapisuje nic. Oczekiwane: 422 i posprzątany katalog. Test: Task 2 `test_convert_output_under_other_name`.
4. Wynik pusty (0 B) przy kodzie 0. Oczekiwane: 422. Test: Task 2 `test_convert_empty_output`.
5. `OSError` przy zapisie wejścia (pełny tmpfs). Oczekiwane: wyjątek leci dalej jako błąd serwera (500), ale katalog i tak jest usunięty. Test: Task 3 `test_oserror_on_copy_cleans_up`.

---

### Task 1: Runner procesu z ubijaniem grupy

**Files:**
- Create: `backend/app/pipeline/converter.py`
- Test: `backend/tests/unit/test_converter_runner.py`

**Interfaces:**
- Produces:
  - `class ConversionError(Exception)`, `class ConverterTimeoutError(ConversionError)`
  - `@dataclass(frozen=True, slots=True) class RunResult: returncode: int; stderr_tail: bytes`
  - `class Runner(Protocol): async def __call__(self, argv: Sequence[str], *, env: Mapping[str, str], cwd: Path, timeout_s: float) -> RunResult`
  - `async def run_process(argv: Sequence[str], *, env: Mapping[str, str], cwd: Path, timeout_s: float) -> RunResult`: implementacja produkcyjna `Runner`
  - `STDERR_TAIL_BYTES = 2048`

- [ ] **Step 1: Write the failing tests** (`sys.executable -c ...` jako proces, `env=dict(os.environ)`, `cwd=tmp_path`)

```python
async def test_run_process_returns_code_and_stderr_tail(tmp_path): ...
    # skrypt: sys.stderr.write("x" * 5000 + "END"); sys.exit(3)
    assert result.returncode == 3
    assert len(result.stderr_tail) == STDERR_TAIL_BYTES and result.stderr_tail.endswith(b"END")

async def test_run_process_timeout(tmp_path): ...
    # skrypt: time.sleep(30), timeout_s=0.5
    with pytest.raises(ConverterTimeoutError): ...
    # całość < 5 s

@pytest.mark.skipif(not hasattr(os, "killpg"), reason="POSIX")
async def test_run_process_timeout_kills_group(tmp_path): ...
    # skrypt: subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]),
    #         zapis pid wnuka do tmp_path/"child.pid", potem time.sleep(30); timeout_s=1
    # po ConverterTimeoutError: w ciągu 2 s os.kill(pid, 0) rzuca ProcessLookupError
    # (dopuszczalny zombie: sprawdzić /proc/<pid>/stat stan "Z", gdy istnieje)

async def test_run_process_cancel_kills_process(tmp_path): ...
    # skrypt zapisuje swój pid do pliku i śpi; task = create_task(run_process(...));
    # czekać na plik, task.cancel(); pytest.raises(CancelledError); proces nie żyje (jak wyżej)
```

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_converter_runner.py -v`. Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `run_process` in `app/pipeline/converter.py`**

`asyncio.create_subprocess_exec(*argv, stdin=DEVNULL, stdout=DEVNULL, stderr=PIPE, cwd=cwd, env=dict(env), start_new_session=hasattr(os, "killpg"))`, potem `asyncio.wait_for(proc.communicate(), timeout_s)`. Przy `TimeoutError` i przy `CancelledError` wywołać `_kill(proc)` (`os.killpg(proc.pid, signal.SIGKILL)`, gdy jest `killpg`, w przeciwnym razie `proc.kill()`; `ProcessLookupError` ignorujemy), potem `await proc.wait()`. Timeout rzuca `ConverterTimeoutError`, anulowanie leci dalej. Zwracamy `RunResult(proc.returncode, stderr[-STDERR_TAIL_BYTES:])`. Docstring modułu: rola modułu i powód ubijania grupy (`soffice` → `oosplash` → `soffice.bin`).

- [ ] **Step 4: Run** tests from Step 2. Expected: PASS (testy POSIX na Windows są SKIPPED). Then `uv run mypy app` and `uv run ruff check app tests`: bez błędów.

- [ ] **Step 5: Commit** `git add app/pipeline/converter.py tests/unit/test_converter_runner.py && git commit -m "feat(pipeline): subprocess runner with process-group kill on timeout"`

---

### Task 2: `LibreOfficeConverter` i wykrywanie `soffice`

**Files:**
- Modify: `backend/app/pipeline/converter.py`
- Modify: `backend/tests/unit/fakes.py` (dodać `FakeRunner`)
- Test: `backend/tests/unit/test_converter.py`

**Interfaces:**
- Consumes: `Runner`, `RunResult`, `ConversionError`, `ConverterTimeoutError`, `run_process` (Task 1); `FileKind` z `app.pipeline.upload_validation.policy`; `Settings.converter_timeout_s`.
- Produces:
  - `class Converter(Protocol): async def convert(self, source: Path, target: FileKind, workdir: Path) -> Path`: zwraca ścieżkę niepustego pliku wynikowego, rzuca `ConversionError` / `ConverterTimeoutError`
  - `class LibreOfficeConverter: __init__(self, soffice_path: str, timeout_s: float, runner: Runner = run_process)`
  - `def find_converter(settings: Settings) -> LibreOfficeConverter | None`: `shutil.which("soffice") or shutil.which("libreoffice")`
  - `def get_converter(request: Request) -> Converter | None`: zależność FastAPI, czyta `request.app.state.converter`
  - `tests/unit/fakes.py`: `FakeRunner(behavior: Literal["ok", "no_output", "other_name", "empty", "exit1", "garbage", "timeout", "oserror", "hang"] = "ok")` z polami `calls: list[list[str]]`, `envs: list[dict[str, str]]`, `started: asyncio.Event`. Przy `"ok"` zapisuje do `--outdir` plik `<stem>.<ext>` z rozszerzeniem z argumentu `--convert-to`. Treść: mały prawdziwy DOCX (`docx.Document().save`) albo XLSX (`openpyxl.Workbook().save`). `"other_name"` zapisuje `wynik.<ext>`, `"empty"` 0 B, `"garbage"` `b"not a zip"`, `"exit1"` zwraca kod 1 bez pliku, `"timeout"` rzuca `ConverterTimeoutError`, `"oserror"` rzuca `FileNotFoundError`, `"hang"` ustawia `started` i czeka bez końca.

Stałe w `converter.py`:
```python
_FILTERS = {FileKind.DOCX: "docx:MS Word 2007 XML", FileKind.XLSX: "xlsx:Calc MS Excel 2007 XML"}
_MACRO_LOCKDOWN_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
"""
```

Argumenty (dokładnie w tej kolejności):
```
[soffice_path, f"-env:UserInstallation={(workdir / 'profile').as_uri()}", "--headless", "--invisible",
 "--norestore", "--nolockcheck", "--nodefault", "--nologo",
 "--convert-to", _FILTERS[target], "--outdir", str(workdir / "out"), str(source)]
```
Środowisko: `{"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(workdir), "TMPDIR": str(workdir), "LANG": "C.UTF-8"}`, `cwd=workdir`.

- [ ] **Step 1: Write the failing tests** (`source = tmp_path / "in" / "input.doc"`, `workdir = tmp_path`)

```python
async def test_convert_doc_returns_output(tmp_path):
    out = await LibreOfficeConverter("/usr/bin/soffice", 60, FakeRunner()).convert(source, FileKind.DOCX, tmp_path)
    assert out == tmp_path / "out" / "input.docx" and out.stat().st_size > 0

async def test_convert_argv_and_env(tmp_path):
    # calls[0] == pełna lista argumentów z planu; brak elementu z nazwą uploadu
    # envs[0]["HOME"] == str(tmp_path) and set(envs[0]) == {"PATH", "HOME", "TMPDIR", "LANG"}

async def test_convert_ods_uses_calc_filter(tmp_path): ...  # "xlsx:Calc MS Excel 2007 XML" w argv, wynik input.xlsx

async def test_convert_seeds_macro_lockdown(tmp_path):
    # (tmp_path/"profile"/"user"/"registrymodifications.xcu").read_text() == _MACRO_LOCKDOWN_XCU
    # i plik istniał w momencie wywołania runnera (FakeRunner sprawdza i zapisuje to w polu)

@pytest.mark.parametrize("behavior", ["no_output", "exit1"])
async def test_convert_failure(tmp_path, behavior): ...   # ConversionError (nie Timeout)
async def test_convert_output_under_other_name(tmp_path): ...  # ConversionError
async def test_convert_empty_output(tmp_path): ...  # ConversionError
async def test_convert_timeout_propagates(tmp_path): ...  # ConverterTimeoutError
async def test_convert_oserror_wrapped(tmp_path): ...  # ConversionError, __cause__ to FileNotFoundError
async def test_convert_rejects_unsupported_target(tmp_path): ...  # ValueError dla FileKind.PDF

def test_find_converter(monkeypatch):
    # monkeypatch shutil.which: None → find_converter(settings) is None;
    # "/usr/bin/soffice" → LibreOfficeConverter z timeout_s == settings.converter_timeout_s
```

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_converter.py -v`. Expected: FAIL (ImportError).

- [ ] **Step 3: Implement** `Converter`, `LibreOfficeConverter`, `find_converter`, `get_converter` in `app/pipeline/converter.py` and `FakeRunner` in `tests/unit/fakes.py`. `convert` tworzy `profile/user/` i `out/`, zapisuje XCU, uruchamia runner, a `OSError` z runnera zamienia na `ConversionError`. Gdy kod wyjścia ≠ 0 albo brakuje niepustego `out/<source.stem>.<target>`, rzuca `ConversionError` i loguje na DEBUG `returncode` oraz `stderr_tail`. Na INFO loguje czas konwersji i `target`.

- [ ] **Step 4: Run** tests from Step 2 + `uv run mypy app` + `uv run ruff check app tests`. Expected: PASS, bez błędów.

- [ ] **Step 5: Commit** `git commit -m "feat(pipeline): LibreOffice converter with per-call profile and macro lockdown"` (pliki z tego zadania)

---

### Task 3: `normalize()`

**Files:**
- Modify: `backend/app/pipeline/normalize.py` (dziś tylko docstring)
- Test: `backend/tests/unit/test_normalize.py`

**Interfaces:**
- Consumes: `Converter`, `LibreOfficeConverter`, `ConversionError`, `ConverterTimeoutError` (Task 2); `FakeRunner`; `ValidatedUpload` z `app.pipeline.upload_validation.validate`; `UploadLimits`, `FileKind`; `inspect_zip_document` z `app.pipeline.upload_validation.containers`; `UploadError`; `AppError`, `ErrorCode`.
- Produces:
  - `@dataclass(slots=True) class NormalizedDocument: kind: FileKind; file: IO[bytes]; converted: bool` + `close()` (zamyka `file` tylko przy `converted`) + `__enter__`/`__exit__`
  - `async def normalize(upload: ValidatedUpload, converter: Converter | None, limits: UploadLimits, *, tmp_dir: str | None = None) -> NormalizedDocument`

Mapowanie: `_TARGETS = {FileKind.DOC: (FileKind.DOCX, "doc"), FileKind.ODS: (FileKind.XLSX, "ods")}`. Komunikat 415: `f"Format .{ext} wymaga LibreOffice, który nie jest dostępny w tej instalacji"`.

- [ ] **Step 1: Write the failing tests** (upload budowany bezpośrednio: `ValidatedUpload(filename="w.doc", extension="doc", kind=FileKind.DOC, mime="application/msword", size_bytes=4, file=BytesIO(b"fake"))`, `tmp_dir=str(tmp_path)`, konwerter: `LibreOfficeConverter("soffice", 60, FakeRunner(...))`)

```python
@pytest.mark.parametrize("kind", [FileKind.PDF, FileKind.DOCX, FileKind.XLSX, FileKind.JPEG, FileKind.PNG])
async def test_passthrough(kind, tmp_path):
    doc = await normalize(upload, None, UploadLimits(), tmp_dir=...)
    assert doc.kind is kind and doc.file is upload.file and not doc.converted

@pytest.mark.parametrize(("kind", "target"), [(FileKind.DOC, FileKind.DOCX), (FileKind.ODS, FileKind.XLSX)])
async def test_converts(kind, target, tmp_path):
    # doc.kind is target, doc.converted, doc.file.tell() == 0, zipfile.is_zipfile(doc.file)
    # FakeRunner.calls[0][-1] kończy się na f"input.{kind}"; list(tmp_path.iterdir()) == []

@pytest.mark.parametrize("kind", [FileKind.DOC, FileKind.ODS])
async def test_no_converter_415(kind, tmp_path):  # AppError.code == UNSUPPORTED_EXTENSION, "LibreOffice" in detail

async def test_timeout_504(tmp_path):  # code == PROCESSING_TIMEOUT; katalog pusty
@pytest.mark.parametrize("behavior", ["exit1", "no_output", "garbage", "oserror"])
async def test_failure_422(behavior, tmp_path):  # code == DOCUMENT_UNREADABLE; katalog pusty
async def test_zip_bomb_output_422(tmp_path):
    # UploadLimits(max_uncompressed_bytes=10) + poprawny DOCX z FakeRunner → DOCUMENT_UNREADABLE

async def test_cancel_cleans_up(tmp_path):
    # FakeRunner("hang"); task; await runner.started.wait(); cancel; CancelledError; katalog pusty
async def test_concurrent_calls_use_separate_profiles(tmp_path):
    # asyncio.gather dwóch normalize na jednym FakeRunner → dwa różne -env:UserInstallation
async def test_upload_stream_rewound(tmp_path):
    # przekonwertowany i przepuszczony: upload.file.tell() == 0 po normalize
async def test_oserror_on_copy_cleans_up(tmp_path, monkeypatch):
    # monkeypatch shutil.copyfileobj → OSError(28, "No space"); pytest.raises(OSError); katalog pusty
async def test_close_ownership():
    # passthrough: close() nie zamyka upload.file; converted: close() zamyka doc.file
```

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_normalize.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement** `normalize` according to design §5.2:
  - formaty spoza `_TARGETS` zwracają wynik od razu;
  - `converter is None` → 415;
  - `TemporaryDirectory(prefix="coi-conv-", dir=tmp_dir)`; `in/input.<ext>` zapisujemy przez `shutil.copyfileobj` po `upload.file.seek(0)`, a w `finally` wracamy na pozycję 0;
  - `await converter.convert(...)`;
  - wynik kopiujemy do `SpooledTemporaryFile(max_size=limits.spool_max_bytes, dir=tmp_dir)`, wywołujemy `inspect_zip_document(spool, target, limits)` i `seek(0)`. Kopiowanie i kontrola idą w `anyio.to_thread.run_sync`;
  - `ConverterTimeoutError` → `AppError(PROCESSING_TIMEOUT)`, potem `ConversionError` i `UploadError` → `AppError(DOCUMENT_UNREADABLE, "Nie udało się przekonwertować pliku .<ext>")`;
  - spool zamykamy przy każdym wyjątku, katalog sprząta `with`. Inne `OSError` lecą dalej.

- [ ] **Step 4: Run** tests from Step 2 + mypy + ruff. Expected: PASS, bez błędów.

- [ ] **Step 5: Commit** `git commit -m "feat(pipeline): normalize DOC/ODS via converter with temp-dir cleanup"`

---

### Task 4: Wykrycie przy starcie i `/health/ready`

**Files:**
- Modify: `backend/app/main.py` (`create_app`)
- Modify: `backend/app/api/v1/health.py`
- Modify: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: `Converter`, `find_converter`, `get_converter` (Task 2).
- Produces: `create_app(settings: Settings | None = None, llm_client: LlmClient | None = None, converter: Converter | None | Literal["auto"] = "auto") -> FastAPI`. Przy `"auto"` wywołuje `find_converter(settings)`. Wynik trafia do `app.state.converter`.

- [ ] **Step 1: Update/write tests in `tests/test_health.py`**: helper `_ready` dostaje parametr `converter: object = <stub>`, gdzie stub to `LibreOfficeConverter("soffice", 60, FakeRunner())`, a istniejące testy zostają bez zmian. Nowe testy:

```python
def test_ready_degraded_converter():  # converter=None, oba modele → 200, {"status": "ok", "degraded": ["converter"]}
def test_ready_degraded_mode_and_converter():  # tylko qwen3:8b, converter=None → degraded == ["fast", "converter"]
def test_create_app_detects_converter(monkeypatch):  # which → None: app.state.converter is None; which → ścieżka: LibreOfficeConverter
```

- [ ] **Step 2: Run** `uv run pytest tests/test_health.py -v`. Expected: nowe testy FAIL.

- [ ] **Step 3: Implement**: parametr `converter` w `create_app`. W `ready` dodać zależność `converter: Annotated[Converter | None, Depends(get_converter)]` i dopisać `"converter"` na koniec `degraded`, gdy `converter is None`. Docstring `ready` uzupełnić o konwerter.

- [ ] **Step 4: Run** `uv run pytest` (całość) + mypy + ruff. Expected: PASS.

- [ ] **Step 5: Commit** `git commit -m "feat(api): detect LibreOffice at startup and report it in readiness"`

---

### Task 5: Test na prawdziwym LibreOffice

**Files:**
- Modify: `backend/pyproject.toml` (`markers`, `addopts`)
- Create: `backend/tests/integration/test_converter_live.py`

**Interfaces:**
- Consumes: `normalize`, `find_converter`; `validate_file`, `UploadLimits` (upload jak w produkcji).

- [ ] **Step 1: pyproject**: `markers = ["llm: wymaga działającej Ollamy", "converter: wymaga LibreOffice (soffice)"]`, `addopts = "-m 'not llm and not converter'"`.

- [ ] **Step 2: Write tests** (`@pytest.mark.converter`; skip, gdy nie ma `MATERIALS = Path(__file__).parents[3] / "materials" / "wniosek-1"` albo `find_converter(Settings(...)) is None`; docstring: `uv run pytest -m converter tests/integration`)

```python
async def test_doc_to_docx_matches_original(tmp_path):
    # validate_file(".doc") → normalize → python-docx; tekst akapitów i komórek tabel po
    # " ".join(s.split()) bez pustych; ≥ 90% elementów z oryginalnego .docx (bez "wizualizacja")
    # występuje w wyniku; tmp_path pusty po zakończeniu
async def test_ods_to_xlsx_matches_original(tmp_path):
    # jak wyżej dla wartości komórek (str, niepuste) ze wszystkich arkuszy vs .xlsx
async def test_parallel_conversions(tmp_path):
    # asyncio.gather(normalize(doc), normalize(ods)) → oba OK (osobne profile się nie blokują)
```

- [ ] **Step 3: Run** `uv run pytest` (domyślnie). Expected: testy `converter` odznaczone (deselected), reszta PASS. Jeśli Docker jest dostępny: `docker compose run --rm api python -m pytest -m converter tests/integration`. W obrazie runtime nie ma pytest ani `tests/`, więc jeśli tego nie da się uruchomić, zapisać w raporcie, że test na żywo nie był uruchamiany.

- [ ] **Step 4: Run** mypy + ruff. Expected: bez błędów.

- [ ] **Step 5: Commit** `git commit -m "test(pipeline): live LibreOffice conversion check behind converter marker"`
