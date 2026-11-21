# Design tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Tokeny designu (kolory, typografia, odstępy, promienie, fokus) w Tailwind 4 z dwoma motywami (`tool` domyślny, `preview` w zakresie `[data-theme="preview"]`), przełącznik motywu w Storybooku i strona dokumentacji „Tokeny”.

**Architecture:** Prymitywy palety jako zwykłe zmienne CSS na `:root` (bez generowania klas). Tokeny semantyczne w `@theme` (nie `@theme inline`), dzięki czemu klasy Tailwind odwołują się do `var(--…)`, a selektor `[data-theme="preview"]` nadpisuje te same zmienne. Domyślna paleta Tailwind jest wyłączona (`--color-*: initial`), więc komponenty mogą użyć tylko nazw semantycznych.

**Tech Stack:** Angular 22, Tailwind CSS 4 (`@tailwindcss/postcss`), Storybook 10.6 (`@storybook/angular-vite`, addon-a11y w trybie `error`, addon-vitest), `@fontsource/open-sans`, `@fontsource/jetbrains-mono`.

**Spec:** `docs/superpowers/specs/2026-11-21-design-tokens-design.md`

## Global Constraints

- Wszystkie polecenia uruchamiaj w `frontend/` po `source ~/.nvm/nvm.sh && nvm use` (Node 24.22.3).
- Wartości tokenów dokładnie jak w tabeli spec (kolory hex, rozmiary px).
- Kontrast tekstu ≥ 4,5:1, obramowań pól ≥ 3:1 (WCAG 2.1 AA). Addon a11y w trybie `error` musi przechodzić.
- Fonty tylko lokalnie z `@fontsource/*` (OFL). Żadnych `<link>` do CDN.
- Komponenty i stories używają wyłącznie klas semantycznych (`bg-surface`, `text-fg`…). Żadnych surowych hexów ani domyślnej palety Tailwind.
- Fokus: `outline` 3px `var(--color-primary)`, `outline-offset: 2px` (outline, nie box-shadow, żeby działał w Windows High Contrast).
- Zależności z jawnym zakresem wersji, bez `latest`.

## Review Focus

1. **Podgląd zagnieżdżony w narzędziu** (`[data-theme="preview"]` wewnątrz strony z motywem tool) musi dostać wartości preview, a elementy poza nim zostać przy tool → test `nested preview overrides only its subtree` w Task 1.
2. **Polskie znaki** (ą ę ł ż ź ć ń ó ś) muszą renderować się fontem Open Sans, a nie fallbackiem → test `Open Sans covers Polish glyphs` w Task 1.
3. **Fokus widoczny w obu motywach** i jako `outline` → test `focus ring is a 3px solid outline` w Task 1.
4. **Domyślna paleta Tailwind wyłączona**: klasa w rodzaju `bg-red-500` nie może generować koloru → test `default palette is disabled` w Task 1.
5. **Przełącznik motywu w Storybooku** musi zmieniać motyw każdego story, a nie tylko stron docs → test `theme global wraps story in data-theme` w Task 2.

---

### Task 1: Tokeny i fonty w CSS + story weryfikujące

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles.css` (importy fontów i tokenów po `@import 'tailwindcss';`)
- Modify: `frontend/package.json` (devDependencies → dependencies: `@fontsource/open-sans@^5`, `@fontsource/jetbrains-mono@^5`)
- Test: `frontend/src/styles/tokens.stories.ts`

**Interfaces:**
- Produces (klasy Tailwind z `@theme`):
  - kolory: `bg`, `surface`, `surface-readonly`, `fg`, `fg-secondary`, `fg-muted`, `primary`, `primary-hover`, `primary-subtle`, `border`, `border-input`, `success`, `success-subtle`, `warning`, `warning-subtle`, `danger`, `danger-subtle`, `topbar`, `on-topbar` → np. `bg-surface`, `text-fg-muted`, `border-border-input`;
  - tekst: `text-body`, `text-label`, `text-title`;
  - odstępy: `py-field-y`, `px-field-x`, `gap-section`, `p-section`;
  - promienie: `rounded-field`, `rounded-card`;
  - fonty: `font-sans` (Open Sans), `font-mono` (JetBrains Mono);
  - klasa narzędziowa `focus-ring` (`@utility`) = outline 3px primary, offset 2px.
- Produces (motyw): atrybut `data-theme="preview"` na dowolnym kontenerze przełącza wartości w jego poddrzewie.

- [x] **Step 1: Zainstaluj fonty**

Run: `npm install @fontsource/open-sans@^5 @fontsource/jetbrains-mono@^5`
Expected: oba pakiety w `dependencies`, bez błędów ERESOLVE.

- [x] **Step 2: Napisz story z testami (play)**

`tokens.stories.ts`: story `Tokens` renderuje szablon z dwiema kolumnami: `<div data-testid="tool">` i `<div data-theme="preview" data-testid="preview">`, w każdej element `data-testid="body"` z klasami `bg-surface text-fg text-body`, element `data-testid="page"` z klasą `bg-bg`, przycisk `data-testid="btn"` z klasą `focus-ring`, element `data-testid="raw"` z klasą `bg-red-500` oraz tekst `Zażółć gęślą jaźń`. Funkcja `play` (z `storybook/test`: `expect`, `within`, `userEvent`) sprawdza:

```ts
// nested preview overrides only its subtree
expect(getComputedStyle(tool.getByTestId('body')).fontSize).toBe('13px');
expect(getComputedStyle(preview.getByTestId('body')).fontSize).toBe('15px');
expect(getComputedStyle(tool.getByTestId('page')).backgroundColor).toBe('rgb(247, 248, 250)');    // #F7F8FA
expect(getComputedStyle(preview.getByTestId('page')).backgroundColor).toBe('rgb(242, 245, 249)'); // #F2F5F9
expect(getComputedStyle(tool.getByTestId('body')).color).toBe('rgb(31, 35, 40)');                 // #1F2328
// default palette is disabled
expect(getComputedStyle(tool.getByTestId('raw')).backgroundColor).toBe('rgba(0, 0, 0, 0)');
// Open Sans covers Polish glyphs
// fonts.check() zwraca true także gdy fontu w ogóle nie ma – dlatego sprawdzamy, że load() znalazł FontFace
const faces = await document.fonts.load('15px "Open Sans"', 'ąęłżźćńóś');
expect(faces.length).toBeGreaterThan(0);
// focus ring is a 3px solid outline
await userEvent.tab(); // fokus na pierwszym btn
const s = getComputedStyle(tool.getByTestId('btn'));
expect([s.outlineStyle, s.outlineWidth, s.outlineOffset]).toEqual(['solid', '3px', '2px']);
expect(s.outlineColor).toBe('rgb(0, 82, 165)'); // #0052A5
```

- [x] **Step 3: Uruchom i potwierdź porażkę**

Run: `npm run test:storybook`
Expected: FAIL na `fontSize` (`16px` zamiast `13px`), bo tokenów jeszcze nie ma.

- [x] **Step 4: Zaimplementuj `src/styles/tokens.css` i importy w `styles.css`**

- `:root` – prymitywy z spec (`--palette-blue-700: #0052A5` itd.), nazwy z prefiksem `--palette-`, żeby nie kolidowały z przestrzenią `--color-*`.
- `@theme { --color-*: initial; --color-bg: #F7F8FA; --color-surface: …; --text-body: 13px; … --font-sans: "Open Sans", system-ui, sans-serif; --font-mono: "JetBrains Mono", ui-monospace, monospace; }` – wartości dla motywu tool z tabeli spec. Kolory semantyczne wskazują na prymitywy (`var(--palette-…)`).
- `[data-theme="preview"] { --color-bg: #F2F5F9; --text-body: 15px; --text-label: 14px; --text-title: 24px; --spacing-field-y: 9px; --spacing-field-x: 12px; --spacing-section: 16px; --radius-card: 8px; }`.
- `@utility focus-ring { &:focus-visible { outline: 3px solid var(--color-primary); outline-offset: 2px; } }`.
- `@layer base { body { @apply bg-bg text-fg font-sans text-body; } }`.
- `styles.css`: `@import 'tailwindcss';`, potem `@import '@fontsource/open-sans/400.css'`, `/600.css`, `/700.css`, `@import '@fontsource/jetbrains-mono/400.css'`, `@import './styles/tokens.css';`.

- [x] **Step 5: Uruchom testy**

Run: `npm run test:storybook && npx ng build`
Expected: PASS (story `Tokens`, w tym a11y), build bez błędów.

- [x] **Step 6: Commit**

```bash
git add frontend/src/styles.css frontend/src/styles frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add design tokens with tool and preview themes"
```

### Task 2: Przełącznik motywu w Storybooku + strona „Tokeny”

**Files:**
- Modify: `frontend/.storybook/preview.ts` (globalTypes `theme`, dekorator)
- Create: `frontend/src/styles/tokens.mdx`
- Test: `frontend/src/styles/theme-switch.stories.ts`

**Interfaces:**
- Consumes: klasy i atrybut `data-theme` z Task 1.
- Produces: global Storybooka `theme: 'tool' | 'preview'` (domyślnie `'tool'`), ikona w toolbarze, dekorator owijający każde story w `<div [attr.data-theme]="theme" class="bg-bg text-fg font-sans text-body min-h-dvh p-section">` (dla `tool` atrybut z wartością `tool`, selektor preview go nie łapie). Kolejne stories komponentów ustawiają motyw przez `globals: { theme: 'preview' }`.

- [x] **Step 1: Napisz story testujące dekorator**

`theme-switch.stories.ts`: komponent z tekstem `Treść` i klasą `text-body`. Dwa stories: `Tool` (bez globals) i `Preview` (`globals: { theme: 'preview' }`). `play`:

```ts
// theme global wraps story in data-theme
const el = canvas.getByText('Treść');
expect(el.closest('[data-theme]')?.getAttribute('data-theme')).toBe('preview'); // w Tool: 'tool'
expect(getComputedStyle(el).fontSize).toBe('15px');                              // w Tool: '13px'
```

- [x] **Step 2: Uruchom i potwierdź porażkę**

Run: `npm run test:storybook`
Expected: FAIL – `closest('[data-theme]')` zwraca `null`.

- [x] **Step 3: Dodaj `globalTypes.theme` (toolbar: „Motyw”, items `tool` → „Narzędzie”, `preview` → „Podgląd e-usługi”) i dekorator `componentWrapperDecorator` w `.storybook/preview.ts`**

Dekorator czyta `context.globals['theme'] ?? 'tool'`.

- [x] **Step 4: Napisz `tokens.mdx`**

Strona „Fundamenty/Tokeny” (`<Meta title="Fundamenty/Tokeny" />`): tabela kolorów semantycznych z próbką, wartością i kontrastem (wartości z spec), skala typografii w obu motywach (próbka w `<div data-theme="preview">`), odstępy, promienie, opis fokusu i zasada „tylko klasy semantyczne”. Próbki budowane klasami Tailwind, bez inline hexów.

- [x] **Step 5: Uruchom testy i build Storybooka**

Run: `npm run test:storybook && npm run build-storybook`
Expected: PASS oba stories, build Storybooka zakończony sukcesem, strona „Fundamenty/Tokeny” w `storybook-static/index.json`.

- [x] **Step 6: Commit**

```bash
git add frontend/.storybook/preview.ts frontend/src/styles/tokens.mdx frontend/src/styles/theme-switch.stories.ts
git commit -m "feat(frontend): add Storybook theme switcher and tokens docs page"
```
