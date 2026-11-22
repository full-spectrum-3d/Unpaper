# Architektura Unpaper

Opis systemu takiego, jaki jest w kodzie. Wymagania konkursu i format importu COI są
w [`../../wymagania/`](../../wymagania/).

## W jednym akapicie

Urzędnik wgrywa blankiet (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) w aplikacji Angular.
API w FastAPI waliduje plik, sprowadza go do wspólnego modelu dokumentu (tekst, OCR,
geometria pól), prosi model językowy (Ollama) o krótki szkic: jakie dane zbiera wniosek,
a deterministyczny kod składa z tego JSON w formacie importu Generatora Formularzy COI
i weryfikuje go regułami z autonaprawą. Każda awaria modelu albo OCR kończy się słabszym,
ale poprawnym formularzem z ostrzeżeniem, nie błędem. Dokumenty nie są nigdzie zapisywane.

```
przeglądarka ──▶ frontend (nginx + SPA) ──/api──▶ api (FastAPI) ──▶ model (Ollama: lokalnie albo zdalnie)
```

## Rozdziały

| # | Dokument | Odpowiada na pytanie |
|---|---|---|
| 1 | [System i wdrożenie](01-system.md) | Z czego składa się system, jak jest wdrożony, gdzie są granice zaufania? |
| 2 | [Pipeline konwersji](02-pipeline.md) | Co dzieje się z plikiem od żądania do odpowiedzi? Co przy awarii? |
| 3 | [Backend](03-backend.md) | Jak jest podzielony kod, co od czego zależy, gdzie dopisać nową rzecz? |
| 4 | [Frontend](04-frontend.md) | Jak działa kolejka importu, podgląd i edytor? Gdzie są dane? |
| 5 | [Testy, jakość, ograniczenia](05-jakosc.md) | Jak sprawdzamy poprawność i jakość AI? Czego system nie robi? |

Do pracy nad konkretnym etapem wystarczy rozdział 2 i tabela modułów w rozdziale 3.

## Decyzje (ADR)

| ADR | Decyzja |
|---|---|
| [0001](adr/0001-ai-rozumie-kod-buduje.md) | Model zwraca tylko szkic semantyczny; JSON składa deterministyczny kod |
| [0002](adr/0002-zawsze-poprawny-formularz.md) | Odpowiedź 200 zawsze zawiera formularz przechodzący weryfikację |
| [0003](adr/0003-strumieniowy-odbior-uploadu.md) | Własny strumieniowy odbiór multipart zamiast `UploadFile` |
| [0004](adr/0004-bezstanowe-przetwarzanie.md) | Bez trwałego zapisu dokumentów i wyników |
| [0005](adr/0005-plaski-schemat-llm-i-naprawa-w-kodzie.md) | Płaski schemat odpowiedzi modelu, naprawa w kodzie zamiast ponowień |

Nowy ADR: kolejny numer, sekcje *Kontekst*, *Decyzja*, *Konsekwencje*; jedna decyzja na plik.

## Pozostałe

- [`wezel-krajowy.md`](wezel-krajowy.md) – ścieżka wdrożenia logowania urzędników przez
  Węzeł Krajowy (login.gov.pl) za brokerem tożsamości. Plan, nie część obecnego rozwiązania.
- [`../openapi.json`](../openapi.json) – kontrakt REST API eksportowany z aplikacji
  (`npm run api:export` w `frontend/`).
- Konfiguracja (zmienne środowiskowe) i uruchomienie: [`../../README.md`](../../README.md).

## Słownik

| Termin | Znaczenie |
|---|---|
| blankiet | dokument źródłowy: papierowy albo elektroniczny wzór wniosku |
| `DocumentModel` | wynik ekstrakcji: strony i bloki tekstu z geometrią, niezależny od formatu |
| szkic (`FormDraft`) | semantyka formularza od modelu albo z reguł: strony, sekcje, pola, warunki |
| sekcja predefiniowana | sekcja z szablonu (`resources/templates/`): dane wnioskodawcy, adres, pełnomocnik, kontakt, zgody |
| strona przedmiotu | strona z polami specyficznymi dla wniosku – jedyna część, którą ustala model |
| autonaprawa | poprawki weryfikatora przed sprawdzeniem reguł, raportowane w `report.fixes` |
| szkic z reguł | szkic bez modelu, z wykropkowań dokumentu (`rule_draft.py`) |
| formularz zastępczy | sekcje predefiniowane + jedno pole „Treść wniosku” (`build_fallback()`) |
