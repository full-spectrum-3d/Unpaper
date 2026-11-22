# 5. Testy, pomiar jakości i znane ograniczenia

## Testy backendu

`make test` (= `cd backend && uv run pytest`). Około 660 testów.

| Katalog | Co sprawdza |
|---|---|
| `tests/unit/` | moduły pipeline'u w izolacji: walidacja uploadu, ekstraktory (PDF generowany w teście: `extract/pdfgen.py`, sztuczny OCR: `fake_ocr.py`), naprawa i normalizacja szkicu, budowa, stany JSONata, weryfikator, klient LLM, JWT, konta |
| `tests/test_*.py` | API przez `TestClient`: endpointy, format błędów, limit ciała, OpenAPI (przykłady w schemacie vs odpowiedzi serwera) |
| `tests/golden/` | builder kontra oficjalne wzorce COI z `wymagania/konfiguracja_form_*.json`; szkice wejściowe w `golden/drafts/` |
| `tests/extraction/` | ekstrakcja na materiałach konkursowych spoza repozytorium (katalog z `COI_MATERIALS_DIR`; bez tej zmiennej test się pomija) |
| `tests/integration/` | z prawdziwą Ollamą, LibreOffice i Tesseractem |

Testy integracyjne mają markery `llm`, `converter`, `ocr` i są domyślnie wyłączone
(`addopts` w `pyproject.toml`). Uruchomienie: `uv run pytest -m llm` itd.

Granica izolacji to `create_app(settings, llm_client, converter)`: testy API podstawiają
klienta modelu z gotowymi odpowiedziami (`tests/unit/fakes.py`,
`tests/fixtures/llm_responses/`) i konwerter albo `None`.

## Testy frontendu

`make test-frontend` (Vitest, ok. 50 plików `*.spec.ts`): reducer i efekty kolejki,
interceptory, guardy, renderer (widoczność, walidatory, odpowiedzi), edytor wyniku.
Komponenty z `shared/ui/` mają stories; `npm run test:storybook` uruchamia je jako testy
z kontrolą dostępności.

`npm run api:check` – kontrakt API: kończy się błędem, gdy `docs/openapi.json` albo
wygenerowany klient różnią się od tego, co produkuje backend.

## Pomiar jakości etapu AI (`backend/llm_eval/`)

Testy jednostkowe nie mówią, czy zmiana promptu albo normalizacji poprawiła formularze.
Do tego służy osobny pomiar na prawdziwych dokumentach.

```
llm_eval/
├── sources/    oryginalne blankiety (PDF, DOCX)
├── cases/      9 przypadków: DocumentModel + oczekiwane pola   ← na nich się stroi
├── holdout/    7 przypadków                                     ← tylko do sprawdzenia
├── build_case.py   plik → przypadek (prawdziwa ekstrakcja z produkcji)
├── run.py          pomiar dla wybranych modeli
├── metrics.py      trafność i precyzja pól, zgodność typu, tytuł
└── accept.py       reguła przyjęcia zmiany względem stanu wyjściowego
```

```bash
cd backend
uv run python -m llm_eval.run --model rules --model qwen3:8b
uv run python -m llm_eval.run --model qwen3:8b --case swietlica
```

`rules` to szkic z reguł bez modelu – dolna granica, z którą model musi wygrywać.

Etykiety są porównywane luźno (podobieństwo znaków albo wspólne rdzenie słów), bo
„Nr działki” i „Numer ewidencyjny działki” to to samo pole. Pola oznaczone `optional` nie
liczą się do trafności, ale ich znalezienie nie jest karane jako nadmiarowe.

Reguła przyjęcia (`accept.py`): zmiana jest odrzucana, jeśli na zbiorze `holdout` średnia
spada o więcej niż 2 pp albo pojedynczy dokument o więcej niż 10 pp. Zbiór `holdout`
istnieje po to, żeby nie dopasować promptu do dziewięciu przypadków strojenia.

Wyniki trafiają do `llm_eval/results/` (poza repozytorium).

## Znane ograniczenia

Stan na 2026-11-22. Każdy punkt jest sprawdzalny w kodzie.

**Brak automatycznego CI.** `.github/workflows/ci.yml` jest pusty (workflow usunięty
w commicie `4541588`). Testy, `ruff`, `mypy` i `api:check` trzeba uruchamiać ręcznie.

**Puste katalogi testów.** `tests/contract/` i `tests/e2e/` zawierają tylko `__init__.py`.
Przepływ przeglądarka → nginx → API → model nie jest testowany automatycznie.

**Numeracja kodów ostrzeżeń nie jest unikalna.** `W27_FORM_REBUILT` i `W27_VARIANT_CHOICE`,
`W28_EXAMPLE_FIELD_REMOVED` i `W28_RODO_CLAUSE_URL_MISSING` mają ten sam numer. Kody są
porównywane jako pełne napisy, więc działanie jest poprawne, ale numer nie identyfikuje
ostrzeżenia. Część kodów jest w `IssueCode`, część to literały w modułach.

**Synchroniczne, długie żądanie.** Konwersja to jedno żądanie HTTP trwające do
`REQUEST_TIMEOUT_S` (540 s). Nie ma kolejki zadań ani identyfikatora do odpytywania.
Każdy pośrednik po drodze (load balancer, proxy) musi mieć timeout większy niż 540 s.

**Limity równoległości w pamięci procesu.** Semafory w `app.state` działają na jedną
instancję API. Przy kilku replikach limit `MAX_CONCURRENT_JOBS` mnoży się przez liczbę
replik, a serwer modelu musi to wytrzymać.

**Wyniki tylko w karcie przeglądarki.** Odświeżenie strony zachowuje sesję
(`sessionStorage`), ale kolejka z wynikami i edycjami jest tylko w pamięci i znika.
To świadoma decyzja o danych osobowych ([ADR 0004](adr/0004-bezstanowe-przetwarzanie.md)),
ale wymaga od urzędnika pobrania wyniku przed zamknięciem karty.

**Klucz JWT bez JWKS.** Po rotacji klucza brokera tożsamości trzeba podmienić
`JWT_PUBLIC_KEY` i zrestartować API ([wezel-krajowy.md](wezel-krajowy.md#6-ograniczenia-i-decyzje)).

**`.env` w repozytorium.** Plik zawiera `JWT_SECRET`, hash hasła konta `admin` i dane
proxy auth serwera modelu na Modalu – tak, żeby `docker compose up` działało bez
konfiguracji. Na każde wdrożenie poza demo trzeba wygenerować nowy `.env`
(`scripts/init-env.sh`) i unieważnić tokeny Modala. `.env` ma też zmienne, których kod nie
czyta (`EXTRACTION_VLM_ENABLED`, `VLM_MODEL`).
