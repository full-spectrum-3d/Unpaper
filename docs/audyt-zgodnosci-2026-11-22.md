# Audyt zgodności z treścią zadania COI — 2026-11-22

Źródło wymagań: `materials/COI - Pełna treść zadania konkursowego.pdf`.
Stan kodu: gałąź `feat/result-editor` (+ niezacommitowany edytor wyniku).
Legenda: ✅ jest, ⚠️ jest z zastrzeżeniem, ❌ brak.

Testy w dniu audytu: backend `pytest` 758 ✔, 17 pominiętych; frontend `tsc` (app) 0 błędów.

## Podsumowanie

Kod pokrywa cały zakres obowiązkowy i wszystkie rozszerzenia 3.3. Brakuje prawie wyłącznie
**materiałów zgłoszeniowych z pkt 4**: wynikowych plików JSON, prezentacji PDF, filmu
i opisu projektu. Największe ryzyko merytoryczne: jakość analizy domyślnym modelem
`qwen3:8b` nie ma zapisanego pomiaru `llm_eval`, a sprawdzian na
obronie (pkt 6) to nowe, nieznane pliki.

## Pkt 4 — wymagania formalne (zgłoszenie)

| Wymaganie | Stan | Uwagi |
|---|---|---|
| Szczegółowy opis i tytuł projektu | ⚠️ | Jest w README („Opis projektu”). Brak osobnego tekstu do formularza zgłoszeniowego. |
| Prezentacja PDF, max 10 slajdów | ❌ | Brak w repo. |
| Wynikowe pliki JSON | ❌ | `out/` pusty. `scripts/convert_all.py` + `make convert-all` gotowe, nie uruchomione. Trzeba wygenerować dla formularzy z 3.1.II, przejrzeć ręcznie i zacommitować. |
| Film ≤ 3 min w otwartym repozytorium (link) | ❌ | Brak. |
| Repozytorium kodu | ✅ | Upewnić się, że jest publiczne w dniu oddania i że `main` zawiera bieżącą pracę. |
| Opcjonalnie: zrzuty ekranu, linki do demo, grafiki | ❌ | Brak `docs/screenshots/`. Tanie do dodania, przydatne w README i prezentacji. |

## Pkt 3.2 — zakres obowiązkowy

| Wymaganie | Stan | Gdzie |
|---|---|---|
| REST API, pojedynczy plik | ✅ | `POST /api/v1/forms/convert` (`backend/app/api/v1/forms.py`) |
| Formaty PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | ✅ | `backend/app/pipeline/extract/`, LibreOffice dla DOC/ODS, Tesseract dla skanów; wielkość liter rozszerzenia bez znaczenia |
| JSON zgodny ze strukturą aplikacji | ✅ | JSON Schema + reguły R01–R15 z autonaprawą; testy `backend/tests/golden/` na wzorcach |
| JSON zgodny ze standardami projektowania | ✅ | strony tematyczne, sekcje predefiniowane, strona FINISH |
| Dokumentacja architektury | ✅ | README „Architektura”, `docs/specyfikacja-techniczna.md`, `docs/architecture/` (+ ADR) |

## Pkt 5 — wymagania techniczne

| Wymaganie | Stan | Uwagi |
|---|---|---|
| Python 3.14+ | ✅ | `requires-python = ">=3.14"`, obraz `python:3.14-alpine3.22` |
| Open source bez copyleftu | ⚠️ | Biblioteki aplikacji permisywne (sprawdzone w metadanych: jedynie `certifi` MPL-2.0 i dev-owe `pathspec`). LibreOffice (MPL-2.0 + zależności LGPL/GPL w Alpine) jako osobny proces — opisane w README „Licencje”. Warto zapytać mentorów, czy to akceptują. |
| Bez zewnętrznych API/SaaS/LLM przez API | ✅ | Ollama lokalnie, sieć `internal`, `OLLAMA_NO_CLOUD`. `scripts/modal_ollama.py` służy tylko do eksperymentów — dopilnować, by nie był opisany jako część rozwiązania. |
| Bez licencji komercyjnych | ✅ | Obraz GPU (NVIDIA) opcjonalny i opisany |
| Walidacja typu + MIME | ✅ | libmagic + struktura archiwów, 415 |
| Nazwa pliku ≤ 250 znaków, bez `; : > < / \ \| ' * % $` | ✅ | `upload_validation/filename.py` |
| Konfigurowalny limit rozmiaru | ✅ | `MAX_FILE_SIZE_MB`, liczony strumieniowo (413) |
| Pliki tylko tymczasowo | ✅ | RAM / tmpfs, katalog per żądanie |
| Docker: oficjalne obrazy, lekkie, wersje, bez `latest`, non-root, tylko potrzebne porty, sekrety w runtime | ⚠️ | API i frontend: Alpine, digest, `USER`. Obraz `llm`: `ubuntu:24.04` + `ollama/ollama` (obraz producenta, nie „Docker Official Image”), bo Ollama nie ma wersji Alpine — uzasadnić w README jednym zdaniem. |
| Konfiguracja: rozmiar, JWT, parametry integracyjne | ✅ | `.env.example`, README „Konfiguracja” |
| README: build, uruchomienie, konfiguracja, REST API | ✅ | wszystkie sekcje są |

## Pkt 3.3 — rozszerzenia (30% oceny za kompletność)

| Rozszerzenie | Stan | Uwagi |
|---|---|---|
| I. Słowniki i dane inicjalne | ✅ | `dictionaryName`, `EXTERNAL_SYSTEM` (PESEL, MLPZ) |
| II. Nowy słownik | ✅ | `report.dictionaryProposals` — tylko w raporcie, nie w samym JSON-ie importu; pokazać na filmie |
| III. Zależności pól/sekcji/stron | ✅ | JSONata w `states`, `flow.links` |
| IV. Frontend do importu | ✅ | Angular, wiele plików, kolejka, podgląd i pobranie JSON |
| V. Wizualizacja eUsługi | ✅ | podgląd formularza z walidacją i stanami |
| VI. Walidacje i UX | ✅ | walidatory PESEL/NIP/REGON/…, batch + ZIP. W toku: edytor wyniku (`feat/result-editor`, niezacommitowany). |

## Pkt 6 — test na nowych plikach podczas obrony

| Ryzyko | Stan | Działanie |
|---|---|---|
| Jakość domyślnego modelu | ❌ | Brak zapisanego pomiaru `llm_eval` dla `qwen3:8b`, który uruchamia się domyślnie. Puścić `llm_eval` na 8B (cases + holdout) i zapisać wynik `--save-baseline`. |
| Tryb regułowy (fallback) | ⚠️ | `rules` = 1,0 tylko na dwóch formularzach wzorcowych; na holdoucie 0–0,5. Jeśli model nie odpowie w czasie, wynik na obronie będzie słaby. |
| Czas konwersji na CPU | ⚠️ | README: 1,5–5 min. Sprawdzić sprzęt na obronę, rozważyć GPU lub wcześniejsze rozgrzanie modelu. |
| Pliki `.JPE` | ⚠️ | W materiałach jest `…psów….JPE`; decyzja Q8 = 415. Zgodne z literą zadania, ale jeśli jury wrzuci `.jpe`/`.jfif`, dostanie błąd. Potwierdzić u mentorów albo akceptować (MIME i tak weryfikowane). |
| Uruchomienie od zera | ⚠️ | Zrobić próbę generalną: czysty klon → `make setup` → `make up` → konwersja, na maszynie docelowej i bez internetu. |

## Pozostałe

- Niezacommitowane zmiany (19 plików + nowe pliki edytora) — dokończyć lub odłożyć przed oddaniem.
- Punkty odłożone z `docs/audyt-2026-11-21.md` (TLS, izolacja parsowania PDF, `prettier`) nie blokują oceny.

## Kolejność prac (sugestia)

1. Pomiar `qwen3:8b` w `llm_eval`, decyzja o modelu.
2. `make convert-all` → przegląd → commit plików do `out/` (z raportami).
3. Domknięcie `feat/result-editor`, merge do `main`.
4. Próba generalna na czystej maszynie.
5. Zrzuty ekranu, prezentacja (≤ 10 slajdów), film (≤ 3 min), opis zgłoszenia.

---

## Dodatek A — przegląd architekta (2026-11-22)

Pkt 5 spełniony w kodzie (digesty, non-root, `read_only`, `cap_drop`, sekrety w runtime, tmpfs, sieć `internal`). Główne ryzyko: czas i współbieżność LLM na CPU. ✔ = potwierdzone ręcznie.

| Waga | Miejsce | Problem | Rekomendacja (nakład) |
|---|---|---|---|
| Krytyczne ✔ | `docker-compose.yml:86`, `backend/app/main.py:86`, frontend `BATCH_CONCURRENCY=2` | 2 zadania naraz, `OLLAMA_NUM_PARALLEL=1`: drugi plik czeka w kolejce Ollamy, zjada `LLM_TIMEOUT_S`, cicho spada na szkic z reguł. | Semafor LLM = `OLLAMA_NUM_PARALLEL`, timeout liczony od wejścia do slotu (S) |
| Krytyczne | `backend/app/api/v1/forms.py:88,150`, `analyze.py:43,300` | Czekanie na slot zjada deadline żądania; 503 dopiero po całym budżecie. | Osobny limit kolejki (np. 30 s) + szybkie 503 z `Retry-After` (S) |
| Krytyczne ✔ | lokalny `.env` | `REQUEST_TIMEOUT_S=180`, `LLM_TIMEOUT_S=120`, `LLM_NUM_CTX=16384` vs `.env.example` 540/240/8192. | Wyrównać przed obroną (S) |
| Krytyczne ✔ | `llm_eval` | Brak pomiaru `qwen3:8b`. | `llm_eval` dla 8B, decyzja CPU/GPU/natywna Ollama z Metal (M) |
| Ważne | `core/config.py:59-63` | `num_predict=2048` nie mieści się w 240 s na CPU; porażka 1. fragmentu = cały dokument na regułach (`analyze.py:270`). | `num_predict` z pozostałego czasu, kolejne fragmenty mimo porażki (S) |
| Ważne | `extract/__init__.py:55-58`, `extract/pdf.py:57` | OCR długich skanów → 504 zamiast częściowego wyniku; parsowania PDF w wątku nie da się przerwać. | Limit OCR + częściowy tekst; PDF w procesie potomnym (M) |
| Ważne ✔ | `pipeline/llm_client.py:66-69`, `core/config.py:77`, `scripts/modal_ollama.py`, `docs/superpowers/plans/2026-11-21-llm-eval-quality.md:15` | Nagłówki Modal (SaaS) w kliencie produkcyjnym, prywatny URL endpointu w śledzonym pliku. | Usunąć nagłówki i URL, skrypt do `tools/experimental` lub poza repo (S) |
| Ważne ✔ | `docs/architecture/README.md` | Zaślepka; `adr/` pusty, link do `openapi.json` w złym miejscu. | Diagram Mermaid + 3–4 ADR (S) |
| Ważne | `.github/workflows/ci.yml` | Brak buildu obrazów, smoke testu compose, kontroli licencji. | Job `docker compose build` + smoke + `pip-licenses --fail-on` (S) |
| Ważne | `forms.py:108-162`, `nginx.conf` | Tylko synchroniczne żądanie do 540 s; LB w COI je urwie. | ADR; ewentualnie `POST /forms/jobs` → 202 (M) |
| Ważne | `backend/app/resources/` | Słowniki/szablony wbudowane w obraz. | `RESOURCES_DIR` z wolumenu RO (S) |
| Ważne | `docker-compose.yml:39,81`, README | Docker Desktop domyślnie 8 GB VM, `llm` ma limit 10g; `MAX_IMAGE_PIXELS=100M` blisko OOM API. | Wymóg ≥14 GB w README, piksele ~40M (S) |
| Drobne | `llm_client.py:13,182`, `converter.py`, `config.py:21` | Pipeline importuje `fastapi.Request`, rzuca `AppError` z kodami HTTP. | DI do `app/api/deps.py` (S) |
| Drobne | `llm_client.py:138-149` | `loaded_models()`/`unload()` tylko dla `llm_eval`. | Przenieść (S) |
| Drobne | `pipeline/draft_*`, `verify.py` | Płaski katalog, długie funkcje (`review.py:232`, `draft_normalize.py:425`). | Podpakiet `pipeline/draft/` (S/M) |
| Drobne | `frontend/nginx.conf` `@login_throttled` | `add_header Retry-After` kasuje dziedziczone nagłówki bezpieczeństwa w 429. | Powtórzyć/`include` (S) |

## Dodatek B — analiza wymagań vs JSON (2026-11-22)

Pokrycie: **53 pozycje „tak”**. Testy `tests/golden` (25 ✔) sprawdzają builder na ręcznych draftach, nie całą konwersję, i **nie** porównują `validation`, `readOnly`, `options`, opisów, layoutu, `flow`.

Pozycje „częściowo” / „nie” (✔ = potwierdzone ręcznie):

| # | Wymaganie | Ocena | Szczegóły |
|---|---|---|---|
| 1 ✔ | Reguła 7: FINISH tylko INFO_SECTION | częściowo | Domyślnie SECTION+TEXT_BLOCK jak wzorce, a `verify.py:566` (W29) ostrzega przy każdym formularzu. |
| 2 | Stany READ_ONLY | nie | Obsługa jest, nic jej nie używa; checkboxy „Brak …” ukrywają pole zamiast blokować. |
| 3 | Warunkowe sekcje z blankietu (3.3.III) | nie | `DraftSection` bez `visible_when`. |
| 4 | Strony alternatywne | nie | D17: `flow` liniowy. |
| 5 | Warunki od pól innych niż wybór | nie | Odrzucane (`fields.py:268-276`). |
| 6 | `tooltipMessage`, wskazówki | częściowo | Zawsze puste; kontrakt LLM nie przenosi opisów. |
| 7 | Oświadczenia neutralne płciowo | częściowo | Dosłownie z blankietu; §8.2 obiecuje przeredagowanie. |
| 8 | Link do klauzuli RODO | częściowo | Tylko z `RODO_CLAUSE_URL`; inaczej W28 przy każdym formularzu. |
| 9 | Adres wg standardu | częściowo | Numer lokalu bez REQUIRED; 5 osobnych CHECKBOX z pustym `title`; etykieta „TERYT_4G_DOWODOWY”. |
| 10 | Multi-select > 5 opcji | częściowo | D18: zawsze CHECKBOX. |
| 11 | Słowniki woj./pow./gm./miejscowość | częściowo | Tylko dokładne etykiety; miejscowość bez słownika. |
| 12 | Nowy słownik (3.3.II) | częściowo | 3 sztywne szablony; nic dla ras psów, rodzajów zajęcia pasa. |
| 13 | Dane inicjalne `readOnly` | częściowo | D10/D19: adres/kontakt edytowalne jak wzorce. |
| 14 | Dane inicjalne w polach przedmiotu | częściowo | Wnioskowanie PESEL.* praktycznie nie startuje (`build/__init__.py:116`). |
| 15 ✔ | Walidacja telefonu (3.3.VI) | nie | Brak walidatora i podpowiedzi formatu. |
| 16 ✔ | Długość pola (3.3.VI) | nie | Brak `maxLength` i informacji o limicie. |
| 17 | Format/rozmiar/liczba plików | częściowo | Tylko tekst w `description`. |
| 18 | KRS, IBAN | częściowo | KRS tylko opis; IBAN nic. |
| 19 | Podsumowanie na FINISH | nie | D16. |
| 20 | Wartości w JSONata zgodne z opcjami | nie | R11 tego nie sprawdza. |

Różnice wobec wzorców widoczne dla jury: `validation` wypełnione (wzorce `[]`), +15 checkboxów „Brak …”, +SELECT numer kierunkowy, dodatkowe REGON/KRS/PESEL, wszędzie `TERYT_4G_DOWODOWY`, zgoda bez `<a>`, inne nazwy strony/sekcji zgody w numerze porządkowym, brak opisów merytorycznych; ścieżka reguł daje zauważalnie inne tytuły i etykiety.

Spec niezgodna z kodem: D11 (checkboxy), D12 (numer kierunkowy), §8.2 (przeredagowanie), D16 (propozycje słowników).

Nowe pytania do mentorów:
1. Jak jury porówna JSON-y: z ukrytym wzorcem (jaka tolerancja na techName/etykiety) czy wg reguł? Od tego zależy, czy dodatki ze standardu dają czy odbierają punkty.
2. Klucz JSON dla „checkboxa wyłączającego pole” i placeholdera; czy osobne pola CHECKBOX są OK?
3. `required` zgody: w `consentSectionConfig` czy przy każdej zgodzie?
4. Etykieta TERYT: „TERYT_4G_DOWODOWY” czy po ludzku?
5. Numer kierunkowy w „Danych do kontaktu” i nazwa słownika?
6. Oświadczenia: dosłownie czy prostym językiem?
7. Czy 3.3.V (wizualizacja) liczy się w ocenie (kryteria numerują inaczej)?

Edytor wyniku (`feat/result-editor`): `form-edit.ts:170-197` zmienia opcje/typ bez aktualizacji `states` — zmiana nazwy opcji po cichu ukrywa sekcje zależne. Brak edycji warunków, opisów, walidatorów poza REQUIRED, `applicant_kinds`.

## Plan po przeglądach (kolejność wg wpływu na ocenę)

| # | Zadanie | Nakład |
|---|---|---|
| 1 | Semafor LLM + budżety czasu (A: krytyczne 1–2, ważne 1) | S |
| 2 | `.env` = `.env.example`, pomiar `qwen3:8b`, decyzja o sprzęcie | M |
| 3 | Usunąć ślady Modala i prywatny URL | S |
| 4 | `make convert-all` → przegląd → commit `out/` | S/M |
| 5 | Usunąć samo-ostrzeżenia W28/W29, zsynchronizować spec (D11, D12, §8.2, D16) | S |
| 6 | Walidacja telefonu, długości, IBAN; opisy pól w kontrakcie LLM | M |
| 7 | R11: wartości JSONata vs opcje; edytor aktualizuje `states` | S/M |
| 8 | `docs/architecture/`: diagram + ADR | S |
| 9 | CI: build obrazów, smoke, licencje | S |
| 10 | Pytania do mentorów (wyżej) — przed decyzją o checkboxach „Brak” i numerze kierunkowym | — |
| 11 | Próba generalna na czystej maszynie; prezentacja, film, zrzuty | M |
