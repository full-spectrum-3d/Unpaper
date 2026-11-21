# Import — dokumenty chronione hasłem (krótki design)

Data: 2026-11-21 · Gałąź: `feat/import-document-password`

**Po co:** backend zwraca 422 `DOCUMENT_PASSWORD_REQUIRED` (brak hasła) i `DOCUMENT_PASSWORD_INVALID` (złe hasło), i oczekuje, że front zapyta o hasło i ponowi żądanie z polem `password` (multipart, maks. 1024 bajty). Dziś front pokazuje ogólny błąd i „Ponów” bez hasła, więc zaszyfrowanego pliku nie da się przetworzyć.

**Cele:** pole hasła w wierszu kolejki przy tych dwóch błędach, ponowienie z hasłem, czytelne komunikaty, dostępność. **Poza zakresem:** pytanie o hasło z góry (front nie wie, który plik jest zaszyfrowany), zapamiętywanie haseł.

**Anty-cele:** hasło w NgRx (DevTools, `sessionStorage`), w logach albo w adresie URL; blokowanie pozostałych plików w partii.

**Podejścia:** A. pole w wierszu kolejki (wybrane), B. okno dialogowe (przerywa partię, przy kilku plikach okna się nakładają), C. pytanie przy dodawaniu (front nie zna szyfrowania z góry).

**Projekt (A):**
- `FileRegistry` (pamięć, poza Store) trzyma też hasło: `setPassword(id, pw)`, `password(id)`, `deletePassword(id)`. `delete(id)` i `clear()` usuwają plik i hasło.
- `ConvertFileFn = (file: File, password?: string) => Observable<unknown>`. HTTP wysyła `password` tylko, gdy jest. Mock (demo offline): plik z „haslo” w nazwie wymaga hasła `test`.
- `QueueItem.passwordState?: 'required' | 'invalid' | null`. `convertFailed` dostaje `passwordState` (rozpoznany z kodu błędu), a nowa akcja `passwordSubmitted({ id })` przywraca wiersz do `pending`. Po `DOCUMENT_PASSWORD_INVALID` efekt usuwa złe hasło z rejestru.
- Komunikaty (`toUserMessage`): `DOCUMENT_PASSWORD_REQUIRED` → „Dokument jest zabezpieczony hasłem. Podaj hasło, aby go przetworzyć.”, `DOCUMENT_PASSWORD_INVALID` → „Hasło jest niepoprawne. Spróbuj ponownie.”
- Wiersz z `passwordState` zamiast „Ponów” pokazuje formularz: `input type="password"`, `autocomplete="off"`, `maxlength="1024"`, etykieta sr-only „Hasło do <nazwa>”, `aria-describedby` na komunikat błędu, przycisk „Odblokuj” (Enter wysyła, pusty submit zablokowany). Po złym haśle pole jest puste i dostaje fokus, jeśli użytkownik właśnie wysłał hasło z tego wiersza.

**Zostawione builderowi:** dokładne klasy (jak istniejące pola i przyciski w kolejce).
