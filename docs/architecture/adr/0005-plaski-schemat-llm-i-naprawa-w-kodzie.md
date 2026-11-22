# ADR 0005: Płaski schemat odpowiedzi modelu i naprawa w kodzie zamiast ponowień

Status: przyjęty · 2026-11-21

## Kontekst

Ollama wymusza kształt odpowiedzi przez *constrained decoding* z JSON Schema (parametr
`format`). Na małych modelach schematy z rekurencją, `anyOf` i `null` dają odpowiedzi
ucięte albo niezgodne. Jedno wywołanie modelu na CPU trwa od kilkudziesięciu sekund do
kilku minut, więc każda ponowna próba to realny koszt dla urzędnika.

Najczęstsze błędy modelu nie dotyczą formatu, tylko spójności: warunek widoczności na polu
tekstowym, odwołanie do nieistniejącego id, powtórzone id, wartość warunku spoza opcji.

## Decyzja

Dwa modele danych zamiast jednego (`backend/app/models/draft.py`):

- **`LlmDraft`** – schemat dla modelu. Płaski (strony → sekcje → pola, bez rekurencji),
  bez `null`, z wartościami domyślnymi (`required=True`, `repeating=False`, puste listy),
  które skracają odpowiedź. Nadmiarowe klucze są ignorowane, a nie odrzucane.
- **`FormDraft`** – kontrakt dla buildera. Ścisły (`extra="forbid"`), z walidatorem
  spójności odwołań.

Przejście `LlmDraft → FormDraft` robi `draft_repair.py`: poprawia odwołania w kodzie
i zgłasza każdą poprawkę ostrzeżeniem. Ponowne wywołanie modelu zostaje tylko dla
odpowiedzi niezgodnej ze schematem (np. ucięty JSON), najwyżej raz i tylko gdy w budżecie
czasu zostało ≥ 1,2 × czasu pierwszego wywołania. Komunikat ponowienia wymienia ścieżki
i treść błędów walidacji.

Oświadczeń model w ogóle nie przepisuje – były najdłuższą częścią odpowiedzi i model je
parafrazował. Bierze je z dokumentu `draft_rules.py`.

## Konsekwencje

- Typowa konwersja to jedno wywołanie modelu.
- Schemat dla modelu i kontrakt buildera zmieniają się niezależnie; zmiana `LlmDraft`
  zmienia schemat przekazywany do Ollamy (`llm_schema()`), więc trzeba ją zmierzyć
  w `llm_eval`.
- Naprawy są widoczne w raporcie, więc urzędnik wie, które warunki widoczności kod
  poprawił albo usunął.
