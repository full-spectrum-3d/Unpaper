# ADR 0004: Bezstanowe przetwarzanie dokumentów

Status: przyjęty · 2026-11-21

## Kontekst

Blankiety wniosków bywają wypełnione: zawierają PESEL, adresy, dane o dochodach i zdrowiu.
Wymaganie konkursu (M5) i RODO: nie przechowywać danych z dokumentów dłużej niż to
konieczne.

## Decyzja

API nie zapisuje dokumentów ani wyników. Każde żądanie przetwarza plik w pamięci
i w plikach tymczasowych, które znikają po jego zakończeniu – także przy błędzie, timeoucie
i anulowaniu:

- upload i wynik LibreOffice: `SpooledTemporaryFile`;
- katalog roboczy LibreOffice: `TemporaryDirectory` na wywołanie; `normalize._in_thread`
  czeka na wątek przed przepuszczeniem anulowania, żeby katalog nie został usunięty, kiedy
  wątek jeszcze w nim pisze;
- `/tmp` kontenera to `tmpfs`, reszta systemu plików jest tylko do odczytu.

Logi zawierają tylko metadane; nazwa pliku jest w nich skrótem SHA-256. Jedyny trwały zapis
API to baza kont (`users.db` na wolumenie `api-data`).

Frontend trzyma wyniki w store NgRx w pamięci karty; do `sessionStorage` trafia tylko
sesja logowania. Pliki i hasła do dokumentów są poza store (`FileRegistry`), żeby nie
trafiły do DevTools.

## Konsekwencje

- Nie ma historii konwersji ani możliwości wrócenia do wyniku z innego urządzenia.
- Odświeżenie lub zamknięcie karty traci wyniki i edycje – urzędnik musi pobrać JSON.
- Skalowanie poziome API jest proste (brak stanu współdzielonego), z zastrzeżeniem
  limitów równoległości w pamięci procesu ([05-jakosc.md](../05-jakosc.md#znane-ograniczenia)).
- Dodanie trwałego zapisu (np. szkiców w bazie) wymaga osobnej decyzji: retencji,
  szyfrowania i podstawy prawnej.
