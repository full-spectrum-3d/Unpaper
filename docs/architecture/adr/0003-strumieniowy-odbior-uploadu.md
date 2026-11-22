# ADR 0003: Własny, strumieniowy odbiór multipart zamiast `UploadFile`

Status: przyjęty · 2026-11-21

## Kontekst

Plik od użytkownika jest niezaufany. Wymagania: dokładnie jeden plik, limit rozmiaru,
odrzucenie złego rozszerzenia i znaków w nazwie, brak śladów na dysku po żądaniu.

Parametr `UploadFile` w FastAPI powoduje wczytanie i sparsowanie całego ciała żądania,
zanim kod endpointu się wykona. Plik `.exe` o rozmiarze 20 MB zostałby w całości przyjęty
tylko po to, żeby go odrzucić; drugi plik w żądaniu też zostałby odebrany.

## Decyzja

`/forms/convert` czyta `request.stream()` i parsuje multipart samodzielnie
(`upload_validation/receive.py`, parser z `python-multipart`):

- nazwa i rozszerzenie są sprawdzane z nagłówka części, zanim przeczytamy treść;
- rozmiar jest liczony w trakcie odbioru, przekroczenie przerywa odbiór;
- druga część z plikiem przerywa odbiór; limity na liczbę części i rozmiar nagłówków;
- treść trafia do `SpooledTemporaryFile` (RAM do `SPOOL_MAX_MB`, potem anonimowy plik
  na `tmpfs`), który znika po zamknięciu.

Opis ciała dla OpenAPI jest podany ręcznie (`openapi_extra` w `forms.py`).

## Konsekwencje

- Odrzucenie złego pliku kosztuje odczyt nagłówka, nie całego ciała.
- Walidacja treści (libmagic, ZIP, PDFium) jest osobnym krokiem w puli wątków pod własnym
  semaforem; powolny klient przy wysyłaniu nie zajmuje miejsca w limicie CPU.
- Klient frontendu dla tego endpointu jest pisany ręcznie (`convert-file.http.ts`), bo
  generator OpenAPI nie zna parametru pliku.
- Kod parsera multipart jest nasz i musi mieć własne testy (`tests/test_forms_api.py`,
  `tests/test_body_limit.py`, `tests/unit/test_upload_*`).
