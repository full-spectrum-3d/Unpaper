# Jakość szkicu LLM – plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Podnieść wynik `llm_eval` na 9 przypadkach do średnio ≥97% trafności i ≥90% precyzji ogólnymi regułami, które nie obniżają wyniku na nowym zestawie kontrolnym, i zakończyć raportem.

**Architecture:** Najpierw pomiar: przypadki z prawdziwej ekstrakcji, zestaw kontrolny `llm_eval/holdout/`, powtórzenia, zapisany stan wyjściowy i automatyczna reguła przyjęcia (`llm_eval/accept.py`). Potem poprawki w `draft_rules.py` / `draft_normalize.py` / `doc_hints.py` / `system.md`. Każdą sprawdza `--compare` z tą samą regułą, na `qwen3.5:35b-a3b` i na `rules`.

**Tech Stack:** Python 3.14, uv, pytest, ruff, mypy strict, Ollama na Modal (L40S).

**Spec:** `docs/superpowers/specs/2026-11-21-llm-eval-quality-design.md`

## Global Constraints

- Model pomiaru: `qwen3.5:35b-a3b` i `rules`. Endpoint: `LLM_BASE_URL=https://kacpertalaga--def-ollama-serve.us-east.modal.run`, a klucze Modal biorą się z root `.env` przez `Settings` i nigdy nie są wypisywane.
- Cel na `cases`: średnia z 3 przebiegów trafność ≥ 97%, precyzja ≥ 90%. Żaden przypadek poniżej 90% trafności / 80% precyzji.
- Reguła przyjęcia (`holdout`, względem stanu wyjściowego, nie poprzedniej zmiany): średnia trafność i średnia precyzja osobno ≥ stan wyjściowy − 2 pp, a pojedynczy dokument nie spada o więcej niż 10 pp. Na `cases` średnie nie spadają.
- Anty-cele: żadnej reguły ani promptu rozpoznającego konkretny dokument (tytuł, „poz. 29”, „D.1”). Żadnego obniżania `MATCH_THRESHOLD` ani aliasów łączących różne pola. Zmiana wzorca przypadku tylko z uzasadnieniem z §4.3 w treści commita.
- Każda reguła ma test jednostkowy na **zmyślonym** przykładzie i co najmniej jeden kontrprzykład, który reguła zostawia.
- Commity: jedna linia, bez stopki o współautorstwie Claude. Zakaz zmian w `frontend/`.
- Pełny `pytest` wiesza się na `python-magic` na tej maszynie. Uruchamiaj: `uv run pytest -q -p no:cacheprovider tests/unit tests/golden tests/integration/test_rule_path.py --ignore=tests/unit/extract/test_extract.py --ignore=tests/unit/test_converter.py --ignore=tests/unit/test_validate_content_kind.py --ignore=tests/unit/test_normalize.py` (z `backend/`). Do tego `uv run ruff check . && uv run ruff format --check . && uv run mypy app`.
- Zimny kontener Modal: przed `llm_eval.run` wyślij `GET /api/tags` z timeoutem 300 s, bo `/api/ps` ma 3 s. Jeśli model nie jest widoczny, zatrzymaj stary kontener (`modal container list`, `modal container stop -y <id>`).
- Budżet GPU: limit 15 USD, a pełny pomiar `all ×3` kosztuje ok. 0,3 USD. Nie przekraczaj ok. 20 pełnych pomiarów.

## Review Focus

- **Etykieta wyliczana, którą wnioskodawca wpisuje sam** („Kwota nadpłaty”, „Kwota dochodu”, „Wysokość dochodu na osobę”) musi zostać. Test kontrprzykładu w Task 5.
- **Numer pozycji przed tekstem informacyjnym albo nagłówkiem** („12. Pouczenie”, „A. DANE SKŁADAJĄCEGO”) nie może stać się polem. Test w Task 6.
- **Sekcja wnioskodawcy z osobnymi polami „Imię” i „Nazwisko”** nie podlega sklejaniu, bo te pola usuwa i tak `applicant_field_reason`, a sklejanie dotyczy tylko innej osoby. Test w Task 7.
- **Przypadek bez odpowiedzi modelu** (fallback na `rules`) w powtórzeniach: średnia liczy go jak każdy inny przebieg, a nie pomija. Test w Task 2.
- **Zestaw kontrolny bez zapisanego stanu wyjściowego**: `--compare` z brakującym przypadkiem w bazie zgłasza naruszenie zamiast cicho przejść. Test w Task 2.

---

### Task 1: Przypadki z prawdziwej ekstrakcji

**Files:**
- Create: `backend/llm_eval/build_case.py`
- Create: `backend/llm_eval/sources/<slug>.<ext>` (9 plików źródłowych, kopie z paczek organizatora w `C:\Users\Kacper Talaga\Downloads\*formularze do cyfryzacji*` oraz `Downloads\Wniosek 1`, `Wniosek 2`; format jak w polu `source` przypadku)
- Delete: `backend/llm_eval/extract.py`
- Modify: `backend/llm_eval/cases/*.json` (tylko klucz `document`)
- Test: `backend/tests/unit/test_llm_eval.py`

**Interfaces:**
- Produces: `build_document(path: Path, settings: Settings) -> DocumentModel` i CLI `uv run python -m llm_eval.build_case <plik> <slug> [--set cases|holdout]`. Zapisuje `document` i `source`, a `expected` zostawia (dla nowego pliku tworzy pusty szablon jak dotychczasowy `extract.py`).

- [ ] **Step 1: Test** `test_build_document_uses_real_extraction`. Zbuduj w teście mały DOCX (`docx.Document()` z akapitem „Imię psa: ………”), zapisz do `tmp_path`, wywołaj `build_document`. Asercje: `doc.source.method == "docx"` oraz istnieje blok `input_placeholder` albo blok z wypełnieniem.
- [ ] **Step 2: Uruchom i sprawdź, że test pada** (brak modułu).
- [ ] **Step 3: Zaimplementuj `build_document`.** Rodzaj pliku z rozszerzenia (`.pdf`, `.docx`, `.xlsx`, `.png`, `.jpg`/`.jpeg` → `FileKind`). `.doc`/`.odt`/`.ods` odrzuć z komunikatem „zapisz jako DOCX/XLSX”. Potem `extract(NormalizedDocument(kind, file, converted=False), settings)` i zwróć `.document`. OCR: domyślny `TesseractOcr`.
- [ ] **Step 4: Test przechodzi.**
- [ ] **Step 5: Przebuduj 9 przypadków** z `llm_eval/sources/`. `test_cases_are_complete` ma przejść. Jeśli `build_document` daje dla któregoś pliku dokument bez treści (np. skan bez Tesseracta), zatrzymaj się i zgłoś, nie zostawiaj starej ekstrakcji po cichu.
- [ ] **Step 6: Commit** `test(llm): build eval cases with the production extractor`

### Task 2: Zestawy, powtórzenia i reguła przyjęcia

**Files:**
- Modify: `backend/llm_eval/run.py` (`load_cases`, `main`, `summary`)
- Create: `backend/llm_eval/accept.py`
- Create: `backend/llm_eval/holdout/.gitkeep`
- Test: `backend/tests/unit/test_llm_eval_accept.py`

**Interfaces:**
- Produces:
  - `load_cases(names: list[str] | None = None, set_name: Literal["cases", "holdout", "all"] = "cases") -> list[dict[str, Any]]`. Każdy przypadek ma dodatkowo `case["set"]`.
  - `aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]` w `accept.py`. Jeden wiersz na (`set`, `case`, `model`) z polami `recall`, `precision` (średnie), `recall_min`, `recall_max`, `precision_min`, `precision_max`, `runs`.
  - `violations(baseline: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[str]`. Oba argumenty to wyjście `aggregate`. Zwraca opisy naruszeń reguły z Global Constraints, a pusta lista oznacza przyjęcie.
  - CLI: `--set cases|holdout|all` (domyślnie `cases`), `--repeat N` (domyślnie 1), `--compare <plik.json>` (porównuje z zapisanym `aggregate`), `--save-baseline <plik.json>`.
  - Każdy wiersz wyników ma `set` i `run` (1…N).

- [ ] **Step 1: Testy** w `test_llm_eval_accept.py`:
  - `test_aggregate_means_and_range`: dwa przebiegi z recall 0.8 i 1.0 dają `recall == 0.9`, `recall_min == 0.8`, `recall_max == 1.0`, `runs == 2`.
  - `test_aggregate_counts_fallback_runs`: wiersz z `fallback=True` i recall 0.5 wchodzi do średniej.
  - `test_violations_empty_when_equal`: `violations(b, b) == []`.
  - `test_violations_holdout_mean_drop_over_2pp`: średnia precyzja holdout niższa o 3 pp daje jedno naruszenie z „holdout” i „precyzja”.
  - `test_violations_single_holdout_doc_drop_over_10pp`: jeden dokument −11 pp przy niezmienionej średniej daje naruszenie z nazwą przypadku.
  - `test_violations_cases_mean_drop`: średnia trafność `cases` −1 pp daje naruszenie.
  - `test_violations_missing_case_in_baseline`: przypadek obecny w `current`, a nieobecny w `baseline` daje naruszenie „brak w stanie wyjściowym”.
  - `test_violations_per_model`: porównanie dla każdego modelu osobno; model nieobecny w `current` nie jest naruszeniem.
- [ ] **Step 2: Testy padają.**
- [ ] **Step 3: Zaimplementuj** `aggregate` i `violations` w `accept.py` oraz `load_cases(set_name)` i flagi w `run.py`. `--repeat` powtarza pętlę przypadków bez ponownego rozgrzewania. `summary` dla `--repeat > 1` pokazuje średnią i zakres min–max. `--compare` wypisuje naruszenia i kończy kodem 1, jeśli są. `--save-baseline` zapisuje `aggregate(rows)`.
- [ ] **Step 4: Testy przechodzą**, razem z istniejącym `test_llm_eval.py`.
- [ ] **Step 5: Commit** `test(llm): repeat eval runs, holdout set and acceptance check`

### Task 3: Zestaw kontrolny

**Files:**
- Create: `backend/llm_eval/sources/holdout/<slug>.<ext>` (7 dokumentów)
- Create: `backend/llm_eval/holdout/<slug>.json`
- Modify: `backend/tests/unit/test_llm_eval.py` (`test_holdout_is_complete`: ≥6 przypadków, każdy z tytułem i polami; nazwy nie pokrywają się z `cases`)

**Interfaces:**
- Consumes: `llm_eval.build_case … --set holdout` (Task 1).

- [ ] **Step 1: Wybierz 7 dokumentów** z publicznych BIP-ów gmin i starostw, „nie za łatwych” (decyzja użytkownika). Muszą być rodzajami spoza 9 przypadków i razem pokrywać:
  - deklarację z numerowanymi pozycjami i tabelą (np. DN-1 / IN-1 podatek od nieruchomości);
  - wniosek z danymi innej osoby (np. o dodatek mieszkaniowy albo o kartę dużej rodziny);
  - wniosek z listami wyboru i warunkami (np. o wycinkę drzew, o zgromadzenie lub imprezę masową);
  - formularz z wartościami wyliczanymi wpisywanymi przez wnioskodawcę (np. deklaracja o dochodach);
  - co najmniej jeden skan (PDF bez tekstu albo JPG), co najmniej jeden DOCX i jeden PDF tekstowy.

  Nie zapisuj w repo danych osobowych. Bierz tylko puste blankiety.
- [ ] **Step 2: Zbuduj przypadki** przez `build_case --set holdout`.
- [ ] **Step 3: Napisz `expected`** według §4.3 specyfikacji (pola przedmiotu sprawy, bez danych wnioskodawcy, podpisu, miejsca i daty, wartości wyliczanych, tekstów informacyjnych i oświadczeń; lista wyboru to jedno pole). Wzorce piszesz **zanim** zobaczysz wynik modelu na tych dokumentach. Pola niejednoznaczne oznacz `optional: true`.
- [ ] **Step 4: `test_holdout_is_complete` przechodzi.**
- [ ] **Step 5: Commit** `test(llm): add holdout eval documents`

### Task 4: Stan wyjściowy

**Files:**
- Create: `backend/llm_eval/baseline.json` (wyjście `aggregate`, commitowane)
- Modify: `docs/` – istniejący dokument wyników LLM z commita 4328498 (znajdź przez `git show --stat 4328498`), nowa sekcja „Pomiar 2026-11-21: stan wyjściowy”

- [ ] **Step 1: Pomiar:** `uv run python -m llm_eval.run --model qwen3.5:35b-a3b --model rules --set all --repeat 3 --save-baseline llm_eval/baseline.json`
- [ ] **Step 2: Wpisz tabelę** (średnia i zakres per przypadek i zestaw) do dokumentu wyników.
- [ ] **Step 3: Commit** `docs(llm): record eval baseline with holdout`

Od tego kroku każda poprawka (Task 5–9) kończy się krokiem „Sprawdzenie”: `… --set all --repeat 3 --compare llm_eval/baseline.json` dla `qwen3.5:35b-a3b` i `rules`. Commit następuje tylko przy kodzie wyjścia 0. Przy naruszeniu zmień regułę albo ją porzuć i zapisz w raporcie (Task 10), dlaczego.

### Task 5: Pola wyliczane i stawki

**Files:**
- Modify: `backend/app/pipeline/draft_rules.py`, `backend/app/pipeline/draft_normalize.py`, `backend/app/resources/prompts/system.md`, `README.md` (lista ostrzeżeń)
- Test: `backend/tests/unit/test_draft_rules.py`, `backend/tests/unit/test_draft_normalize.py`

**Interfaces:**
- Produces: `computed_field_reason(label: str, section_labels: list[str]) -> str | None` w `draft_rules.py` i ostrzeżenie `W33_COMPUTED_FIELD_REMOVED` (komunikat: `Usunięto pole „{label}”: {reason}.`).

Reguła: etykieta zaczyna się od słowa wyliczanego („stawka”, „wysokość … opłaty”, „kwota … opłaty”, „suma”, „razem”, „łącznie”, „ogółem”) albo odwołuje się do innej pozycji („z poz.”, „poz. N + poz. M”, „pomniejszona o”), **i** w tej samej sekcji jest pole `number` o etykiecie spoza tej reguły. Bez drugiego warunku pole zostaje.

- [ ] **Step 1: Testy** (`test_draft_rules.py`):
  - `test_computed_labels_removed`, parametryzowany: („Stawka opłaty za gospodarstwo”, [„Liczba gospodarstw”]), („Wysokość miesięcznej opłaty (do 50 m²)”, [„Liczba lokali do 50 m²”]), („Suma opłat pomniejszona o zwolnienie”, [„Liczba osób”]), („Kwota z poz. 12 załącznika”, [„Liczba osób”]). Asercja: wynik nie jest `None`.
  - `test_entered_amounts_kept`, parametryzowany: („Kwota nadpłaty”, [„Rok podatkowy”]), („Wysokość dochodu na osobę”, []), („Kwota dochodu”, [„Liczba osób w rodzinie”]), („Łączna powierzchnia zajęcia (m²)”, []). Asercja: `None`.
  - W `test_draft_normalize.py`: `test_computed_fields_removed_with_warning`. Szkic z sekcją [„Liczba gospodarstw” number, „Stawka opłaty” number] traci tylko drugie pole i dostaje `W33_COMPUTED_FIELD_REMOVED`.
- [ ] **Step 2: Testy padają.**
- [ ] **Step 3: Zaimplementuj** regułę i wywołaj ją w `normalize_draft` obok `_remove_applicant_fields`. Dopisz zasadę w `system.md`: nie twórz pól na wartości, które system wylicza z innych pól, ani na stawki z cennika. Przykład w prompcie ma być ogólny, bez słów z przypadków. Dopisz `W33` do listy ostrzeżeń w `README.md`.
- [ ] **Step 4: Testy i lint przechodzą.**
- [ ] **Step 5: Sprawdzenie** (`--compare`).
- [ ] **Step 6: Commit** `fix(llm): drop computed amount and rate fields`

### Task 6: Numerowane pozycje deklaracji jako pola

**Files:**
- Modify: `backend/app/pipeline/doc_hints.py` i/lub `system.md` (wybór należy do wykonawcy, decyzja §7 specyfikacji)
- Test: `backend/tests/unit/test_doc_hints.py`

**Interfaces:**
- Produces (jeśli przez `doc_hints`): `annotate_choices` oznacza blok `label`/`paragraph` w postaci `^\d{1,3}\.\s+<etykieta do 6 słów>$`, bez wypełnienia, po którym nie ma od razu bloku z wypełnieniem, jako pole: dokleja `FIELD_MARKER` do tekstu.

- [ ] **Step 1: Testy:**
  - `test_numbered_position_becomes_field`: bloki [„26. Miejscowość”, „27. Ulica”] dostają znacznik pola.
  - `test_numbered_heading_or_notice_kept`: „12. Pouczenie”, „A. DANE SKŁADAJĄCEGO”, „3. Do wniosku należy dołączyć dokumenty potwierdzające prawo do nieruchomości” nie dostają znacznika (słowo z listy informacyjnej: pouczenie, objaśnienia, informacja, uwaga; więcej niż 6 słów; wersaliki).
  - `test_numbered_position_with_fill_unchanged`: „26. Miejscowość ……” zostaje bez zmian.
- [ ] **Step 2: Testy padają.**
- [ ] **Step 3: Zaimplementuj.**
- [ ] **Step 4: Testy przechodzą.**
- [ ] **Step 5: Sprawdzenie** (`--compare`).
- [ ] **Step 6: Commit** `fix(llm): treat numbered declaration positions as fields`

### Task 7: Imię i nazwisko innej osoby jako jedno pole

**Files:**
- Modify: `backend/app/pipeline/draft_normalize.py`
- Test: `backend/tests/unit/test_draft_normalize.py`

**Interfaces:**
- Produces: ostrzeżenie `W34_NAME_PARTS_MERGED`. W sekcji dotyczącej innej osoby (`_OTHER_PERSON` z `draft_rules`, wystawione jako `is_other_person_section(titles: list[str]) -> bool`) sąsiednie pola „Imię …” i „Nazwisko …” (`short_text`) zastępujemy jednym polem „Imię i nazwisko …”. Sufiks bierzemy z pola „Imię”, a id z pierwszego pola.

- [ ] **Step 0: Sprawdź standard.** W `wymagania/HackNation - Standardy i dobre praktyki projektowania formularzy.md` i we wzorcach `wymagania/konfiguracja_form_*.json` sprawdź, czy dane innej osoby mają imię i nazwisko razem. Jeśli standard je rozdziela, **nie rób tej poprawki**. Wtedy popraw wzorzec `stypendium` (uzasadnienie w commicie: standard) i zapisz to w raporcie.
- [ ] **Step 1: Testy:**
  - `test_other_person_name_parts_merged`: sekcja „Dane kandydata” z [„Imię kandydata”, „Nazwisko kandydata”] daje [„Imię i nazwisko kandydata”] oraz `W34`.
  - `test_applicant_section_not_merged`: sekcja „Dane wnioskodawcy” zostaje bez zmian (pola usuwa wcześniejsza reguła, ta ich nie skleja).
  - `test_non_adjacent_name_parts_not_merged`: [„Imię”, „Data urodzenia”, „Nazwisko”] w „Dane dziecka” zostaje bez zmian.
- [ ] **Step 2: Testy padają.**
- [ ] **Step 3: Zaimplementuj.** Dopisz `W34` w `README.md`.
- [ ] **Step 4: Testy przechodzą.**
- [ ] **Step 5: Sprawdzenie** (`--compare`).
- [ ] **Step 6: Commit** `fix(llm): merge first and last name of another person`

### Task 8: Diagnoza pojedynczych pominięć

**Files:**
- Modify: zależnie od przyczyny (`analyze.py`, `draft_normalize.py`, `doc_hints.py`, `system.md`)
- Test: test jednostkowy reguły, która była przyczyną

- [ ] **Step 1:** Dla każdego pola z `missing` w ≥2 z 3 przebiegów (na `cases` i `holdout`) ustal, czy pole jest w `doc.to_prompt_text()`, w surowej odpowiedzi modelu i po `normalize_draft`. Zapisz tabelę „pole → etap, na którym ginie” w notatce do raportu.
- [ ] **Step 2:** Dla przyczyn w kodzie (reguła usuwa pole, prompt wycina blok) napisz test odtwarzający przyczynę na zmyślonym przykładzie, napraw ją, sprawdź (`--compare`) i zacommituj (`fix(llm): …`, jeden commit na przyczynę). Pominięcia występujące w 1 z 3 przebiegów to szum, więc tylko je opisz.

### Task 9: Dopasowanie w metryce

**Files:**
- Modify: `backend/llm_eval/metrics.py` albo `aliases` w `cases/*.json`
- Test: `backend/tests/unit/test_llm_eval.py`

- [ ] **Step 1:** Z ostatniego pomiaru wypisz pary (brakujące pole wzorca, nadmiarowe pole szkicu) w tej samej sekcji, które opisują to samo pole (np. „Liczba dni” / „Czas trwania (dni)”).
- [ ] **Step 2:** Dla każdej pary dodaj alias we wzorcu. Gdy wzorzec jest ogólny, popraw `similarity`. Do `test_similar_labels` dodaj tę parę, a do `test_different_labels` parę podobną, ale różną (np. „Liczba dni” / „Liczba osób”).
- [ ] **Step 3: Testy przechodzą. `--rescore` ostatniego wyniku** pokazuje zmianę tylko dla tych par.
- [ ] **Step 4: Commit** `test(llm): match same fields named differently`

### Task 10: Raport

**Files:**
- Modify: dokument wyników LLM w `docs/` (ten z Task 4)

- [ ] **Step 1: Pomiar końcowy** `--set all --repeat 3` dla `qwen3.5:35b-a3b` i `rules`.
- [ ] **Step 2: Sekcja „Pomiar 2026-11-21: wynik końcowy”** zawiera:
  - tabelę stanu wyjściowego i końcowego per przypadek na obu zestawach;
  - listę przyjętych i odrzuconych poprawek z wynikiem `--compare`;
  - pozostałe błędy z przyczyną (z Task 8);
  - czy cele z §2 są osiągnięte, a jeśli nie, czy podejście B (dwa modele, głosowanie) albo C (recenzent) by pomogło i jakim kosztem czasu.
- [ ] **Step 3: Commit** `docs(llm): report eval quality round`
