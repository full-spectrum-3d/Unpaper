# ADR 0001: AI rozumie, kod buduje

Status: przyjęty · 2026-11-21

## Kontekst

Wynik ma być JSON-em w formacie importu Generatora Formularzy COI: kilkadziesiąt do kilkuset
KB, sztywne reguły (unikalne `id` i `techName`, siatka `x/y/rows/cols`, `flow`, zapytania
JSONata, słowniki, dane inicjalne, strona końcowa tylko informacyjna). Rozwiązanie musi
działać na lokalnym modelu klasy 8B na CPU.

Mały model generujący taki JSON bezpośrednio myli się w szczegółach, które nie wymagają
rozumienia dokumentu, a generacja trwa długo (tokeny wyjścia na CPU są drogie).

## Decyzja

Model zwraca tylko **szkic semantyczny** (`LlmDraft`, `backend/app/models/draft.py`): tytuł,
adresat, kto może złożyć wniosek, strony → sekcje → pola z etykietą, rodzajem (8 wartości),
wymagalnością, opcjami i warunkiem widoczności.

Wszystko, co da się opisać regułą, robi deterministyczny kod w `pipeline/build/`:
identyfikatory, `techName`, układ siatki, sekcje predefiniowane (dane wnioskodawcy, adres,
pełnomocnik, kontakt, zgody), walidatory i słowniki z znaczenia etykiety, dane inicjalne,
składnia JSONata, `flow`. Również to, co można odczytać z dokumentu bez rozumienia
(oświadczenia, pola dublujące dane wnioskodawcy), robi kod (`draft_rules.py`,
`draft_normalize.py`).

## Konsekwencje

- Odpowiedź modelu jest krótka (kilkaset tokenów), więc konwersja na CPU mieści się
  w minutach, a nie dziesiątkach minut.
- Wynik jest strukturalnie poprawny niezależnie od jakości modelu; przy awarii modelu ten
  sam builder pracuje na szkicu z reguł ([ADR 0002](0002-zawsze-poprawny-formularz.md)).
- *Prompt injection* w dokumencie nie może zmienić struktury wyniku ani wywołać akcji:
  model wypełnia sztywny schemat, kod niczego z niego nie wykonuje.
- Model można wymienić bez zmian w kodzie (`LLM_MODEL`); jakość mierzy `llm_eval`.
- Koszt: wiedza domenowa o formularzach COI jest w kodzie i szablonach (`build/`,
  `resources/templates/`). Nowa sekcja predefiniowana albo nowy rodzaj pola to zmiana kodu,
  nie promptu.
