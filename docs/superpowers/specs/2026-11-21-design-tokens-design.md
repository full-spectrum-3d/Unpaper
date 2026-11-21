# Design tokens – narzędzie i podgląd e-usługi

Data: 2026-11-21 · Rozmiar: mała zmiana (krótki design)

## Cel
Jedno źródło prawdy dla kolorów, typografii, odstępów, promieni i fokusu we frontendzie (Angular + Tailwind 4), z którego korzystają wszystkie własne komponenty w Storybooku. Aplikacja ma dwie powierzchnie:
- **narzędzie urzędnika**: zwarte, robocze (import, kolejka, JSON, raport),
- **podgląd e-usługi**: wierne odwzorowanie wyglądu z materiałów COI, bo jury porównuje wynik z docelową e-usługą.

## Cele / poza zakresem / anty-cele
- Cele: tokeny w `@theme`, dwa motywy (`tool` domyślny, `preview` przez `data-theme="preview"`), przełącznik motywu w Storybooku, strona dokumentacji tokenów w Storybooku.
- Poza zakresem: komponenty (osobny krok), tryb ciemny, logotypy i godło (nie kopiujemy znaków instytucji, tylko styl).
- Anty-cele: kolory zapisane na sztywno w komponentach, kontrast poniżej WCAG 2.1 AA, fonty z zewnętrznego CDN (zadanie zabrania zewnętrznych zależności w działaniu).

## Podejścia
- **A. Nazwy semantyczne + nadpisanie w zakresie `[data-theme="preview"]`** (wybrane przez użytkownika). Te same komponenty, inne wartości zmiennych w podglądzie.
- B. Dwa osobne zestawy klas `tool-*` / `pv-*`: odrzucone, bo podwaja style wspólnych komponentów.
- C. Style Dictionary z JSON: odrzucone, bo to nowa zależność i dodatkowy krok budowania bez korzyści przy jednym projekcie.

## Decyzje użytkownika
- Wariant B motywów: wspólna baza, dwa motywy.
- Narzędzie: ciemny granatowy pasek górny (wariant 2 z makiety).
- Implementacja tokenów: podejście A.

## Tokeny (propozycja z makiety, kontrast policzony)
Prymitywy (paleta): `blue-700 #0052A5` (7,6:1 na białym), `blue-800 #003F80`, `blue-50 #EAF2FB`, `ink-900 #1F2328`, `ink-700 #34383F`, `ink-500 #5B6470` (6,0:1), `ink-400 #6E7781` (4,6:1), `line #D5DBE2`, `page #F2F5F9`, `navy #14233C`, `green #136C2E` / `#E6F4EA`, `amber #7A4F00` / `#FFF4D6`, `red #B3261E` / `#FCE8E6`.

Semantyczne (używane przez komponenty):

| Token | tool | preview |
|---|---|---|
| `--color-bg` | `#F7F8FA` | `#F2F5F9` |
| `--color-surface` | `#FFFFFF` | `#FFFFFF` |
| `--color-surface-readonly` | `#F4F6F8` | `#F4F6F8` |
| `--color-fg` / `-secondary` / `-muted` | ink-900 / ink-700 / ink-500 | to samo |
| `--color-primary` / `-hover` / `-subtle` | blue-700 / blue-800 / blue-50 | to samo |
| `--color-border` / `--color-border-input` | line / ink-400 | to samo |
| `--color-success` / `-warning` / `-danger` (+ `-subtle`) | green / amber / red | to samo |
| `--color-topbar` / `--color-on-topbar` | navy / `#FFFFFF` | (nieużywane) |
| `--text-body` | 13px | 15px |
| `--text-label` | 13px | 14px |
| `--text-title` | 16px | 24px |
| `--spacing-field-y` / `--spacing-field-x` | 5px / 8px | 9px / 12px |
| `--spacing-section` | 12px | 16px |
| `--radius-field` / `--radius-card` | 4px / 6px | 4px / 8px |
| fokus | obrys 3px `primary`, offset 2px | to samo |

Typografia: Open Sans (tekst) i JetBrains Mono (JSON), self-hosted przez `@fontsource/*` (licencja OFL).

## Zostawione wykonawcy
- Dokładna składnia Tailwind 4 (`@theme` dla prymitywów i semantyki, `@layer base` lub selektor `[data-theme="preview"]` dla nadpisań).
- Dekorator Storybooka z przełącznikiem motywu (globals/toolbar).
- Strona MDX „Tokeny” z próbkami kolorów, kontrastem i skalą typografii.
- Test: story strony tokenów przechodzi addon a11y w trybie `error`.
