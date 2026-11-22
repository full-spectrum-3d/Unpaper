# ADR 0002: Odpowiedź 200 zawsze zawiera poprawny formularz

Status: przyjęty · 2026-11-21

## Kontekst

Etapy z niepewnym wynikiem: OCR (skany niskiej jakości), model (timeout, niedostępny
serwer, ucięty JSON, błędne odwołania między polami) i sam builder (kombinacje szkicu,
których reguły nie przewidziały). Urzędnik, który dostaje błąd 5xx, nie ma nic; urzędnik,
który dostaje niepełny, ale poprawny formularz z listą braków, może go dokończyć w edytorze.

## Decyzja

Przy pliku, który przeszedł walidację, `/forms/convert` zwraca 200 z formularzem
przechodzącym weryfikację. Każde obniżenie jakości to ostrzeżenie w raporcie, nie błąd
żądania. Łańcuch zastępstw:

| Awaria | Co zamiast | Ostrzeżenie |
|---|---|---|
| strona skanu nierozpoznana | pusta strona | `W11_OCR_UNAVAILABLE` |
| fragment długiego dokumentu (poza pierwszym) | szkic z pozostałych fragmentów | `W14_PARTIAL_ANALYSIS` |
| błędne odwołania w odpowiedzi modelu | naprawa w kodzie (`draft_repair.py`) | `W18`, `W21`, `W22` |
| model: timeout, brak serwera, niepoprawna odpowiedź | szkic z reguł (`rule_draft.py`) | `W01_LLM_FALLBACK`, `W24_RULE_BASED_DRAFT` |
| reguły nie znalazły pól | formularz z sekcjami predefiniowanymi i polem „Treść wniosku” | `W01_LLM_FALLBACK` |
| zbudowany formularz nie przechodzi weryfikacji po autonaprawie | jak wyżej, z tytułem i organem ze szkicu | `W27_FORM_REBUILT` |

Błędem żądania kończą się tylko: plik nie do przyjęcia (4xx), przekroczony czas przed
etapem analizy (504), brak miejsca w kolejce (503) i formularz zastępczy, który sam nie
przechodzi weryfikacji (500 – błąd w kodzie, nie w danych).

## Konsekwencje

- Klient musi czytać `report.warnings` (albo przynajmniej `X-Conversion-Warnings`):
  200 nie oznacza, że formularz jest kompletny.
- `analyze()` nie rzuca z powodu modelu (ścieżki fallbacku: `tests/unit/test_analyze.py`),
  a `verify_form()` zamienia każdy wyjątek reguły lub naprawy na problem `SCHEMA`.
  Nowy kod w tych miejscach musi zachować tę własność.
- Szkic z reguł musi przechodzić tę samą normalizację co szkic modelu, żeby builder miał
  jeden kontrakt wejściowy (`FormDraft`).
