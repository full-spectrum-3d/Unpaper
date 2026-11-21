# Komponenty bazowe UI – ekran importu

Data: 2026-11-21 · Rozmiar: mała zmiana (krótki design)

## Cel
Zestaw własnych komponentów bazowych w Storybooku, z których najpierw powstanie ekran **Import** z kolejką plików (§9.1 specyfikacji). Komponenty korzystają wyłącznie z tokenów semantycznych (`docs/superpowers/specs/2026-11-21-design-tokens-design.md`) i działają w obu motywach (`tool`, `preview`).

## Cele / poza zakresem / anty-cele
- Cele: topbar, button, badge, card, file-drop, progress, table. Każdy ma story z play testem, przechodzącym addon a11y w trybie `error` w obu motywach.
- Poza zakresem: ekran Import jako całość, store `import-queue`, współbieżność, ZIP (następny krok). Pola formularza podglądu (select, datepicker itd.) to osobny krok.
- Anty-cele: surowe hexy i domyślna paleta Tailwind w komponentach, kolor jako jedyny nośnik statusu, `div` udający przycisk, nowe zależności.

## Podejścia
- **1. Komponenty Angular na natywnych elementach** (wybrane przez użytkownika). Selektory atrybutowe tam, gdzie natywny element niesie semantykę (`button[appButton]`, `table[appTable]`), a komponenty elementowe dla reszty. Warianty typowane, inputy jako signals.
- 2. Klasy CSS `@utility` + komponenty tylko z zachowaniem: odrzucone, bo warianty są niewalidowane, a dokumentacja w Storybooku słabsza.
- 3. Angular CDK / `@angular/aria`: odrzucone na teraz, bo ten zestaw nie ma overlayów ani listboxów. Wrócimy przy polach formularza.

## Decyzje użytkownika
- Kolejka w formie **tabeli** (makieta A): kolumny Plik / Rozmiar / Status / Akcje, a nad tabelą licznik i „Pobierz wszystkie (ZIP)”.
- Akcje w wierszu: „Otwórz wynik” (gotowe), „Ponów” i „Usuń” (błąd), „Usuń” (oczekuje). Bez „Anuluj” i „Wyczyść gotowe”.
- Błąd walidacji klienta (reguły §6.3 pkt 2–5) to wiersz kolejki ze statusem „Błąd” i komunikatem pod nazwą pliku, a nie osobny alert.
- Pasek postępu nieokreślony (animacja, bez procentów).
- Dozwolone formaty w opisie strefy wg §6.3: PDF, DOC, DOCX, ODS, XLSX, JPG, PNG. Limit z `MAX_FILE_SIZE_MB` (komponent dostaje go jako input).

## Komponenty
Lokalizacja: `frontend/src/app/shared/ui/<nazwa>/` (`<nazwa>.ts` + `<nazwa>.stories.ts`), prefiks `app`, standalone, `ChangeDetectionStrategy.OnPush`.

| Komponent | API | Uwagi |
|---|---|---|
| `button[appButton]` | `variant: 'primary' \| 'secondary' \| 'ghost'` (domyślnie `secondary`) | natywny `disabled`, fokus z tokenu |
| `app-badge` | `status: 'pending' \| 'processing' \| 'done' \| 'error'` | ikona + tekst PL (Oczekuje / Przetwarzanie / Gotowe / Błąd), kolory `*-subtle`/`*` |
| `app-card` | sloty: `[cardTitle]`, `[cardActions]`, treść | `bg-surface`, `border`, `radius-card` |
| `app-topbar` | `appName`, `userName`, linki przez treść, output `logout` | `bg-topbar`/`text-on-topbar`, `<header>` + `<nav aria-label>` |
| `app-file-drop` | `accept: string`, `maxSizeMb: number`, output `filesSelected: File[]` | ukryty `<input type="file" multiple>`, przycisk „Wybierz pliki”, drag & drop, stan „przeciąganie”, opis formatów i limitu przez `aria-describedby`. Nie waliduje, tylko emituje |
| `app-progress` | `label: string` | `role="progressbar"` bez `aria-valuenow` (nieokreślony), animacja wyłączona przy `prefers-reduced-motion` |
| `table[appTable]` | – | style nagłówka i wierszy na klasach semantycznych |

## Zostawione wykonawcy
- Ikony statusu (znak tekstowy lub inline SVG, z `aria-hidden`).
- Dokładne klasy Tailwind i stany hover/active.
- Story „Kolejka (kompozycja)” składające card + table + badge + button + progress jak w makiecie A, jako test integracji wizualnej.
