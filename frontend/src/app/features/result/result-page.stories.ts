import { provideRouter } from '@angular/router';
import { provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { expect, spyOn, userEvent, waitFor, within } from 'storybook/test';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { mockReport } from '../import/mock-report';
import { formatJson } from './json-lines';
import { QueueItem, importQueueFeatureKey } from '../../store/import-queue/import-queue.reducer';
import { ResultPage } from './result-page';

const done: QueueItem = {
  id: 'd1',
  name: 'Deklaracja o wysokości opłaty.docx',
  size: 84 * 1024,
  status: 'done',
  error: null,
  retryable: false,
  result: nadplata,
  report: null,
  startedAt: 0,
  durationMs: 12000,
};

const notAForm: QueueItem = { ...done, id: 'n1', result: { foo: 1 } };
const withReport: QueueItem = { ...done, id: 'r1', report: mockReport(nadplata) };

const meta: Meta<ResultPage> = {
  title: 'Ekrany/Wynik',
  component: ResultPage,
  decorators: [
    applicationConfig({
      providers: [
        provideRouter([]),
        provideMockStore({
          initialState: {
            [importQueueFeatureKey]: {
              ids: [done.id, notAForm.id, withReport.id],
              entities: { [done.id]: done, [notAForm.id]: notAForm, [withReport.id]: withReport },
            },
          },
        }),
      ],
    }),
  ],
};
export default meta;
type Story = StoryObj<ResultPage>;

const backPath = (c: ReturnType<typeof within>, name: string) =>
  new URL((c.getByRole('link', { name }) as HTMLAnchorElement).href).pathname;

const previewMessage = 'Nie można wyświetlić podglądu: wynik nie ma struktury formularza.';

const tab = (c: ReturnType<typeof within>, name: string) => c.getByRole('tab', { name });
// The JSON view is rendered only while its tab is active.
const jsonRegion = (c: ReturnType<typeof within>) => c.getByLabelText('Wynik konwersji w formacie JSON');

export const Done: Story = {
  args: { id: 'd1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByRole('heading', { level: 1, name: done.name })).toBeVisible();
    const title = await c.findByRole('heading', { level: 2, name: nadplata.title });
    expect(title.closest('[data-theme="preview"]')).not.toBeNull();
    expect(title.closest('main')).not.toBeNull();
    expect(c.queryByText(previewMessage)).toBeNull();
    expect(c.queryByRole('button', { name: 'Podgląd formularza' })).toBeNull();

    const tablist = c.getByRole('tablist', { name: 'Widok wyniku' });
    const tabs = within(tablist).getAllByRole('tab');
    expect(tabs.map((t) => t.textContent?.trim())).toEqual(['Podgląd formularza', 'JSON', 'Raport', 'Edycja']);
    for (const t of tabs) {
      const panel = canvasElement.querySelector(`#${t.getAttribute('aria-controls')}`)!;
      expect(panel).toHaveAttribute('role', 'tabpanel');
      expect(panel).toHaveAttribute('aria-labelledby', t.id);
    }
    const [preview, json, report, edit] = tabs;
    expect(preview).toHaveAttribute('aria-selected', 'true');
    expect(preview).toHaveAttribute('tabindex', '0');
    expect(json).toHaveAttribute('aria-selected', 'false');
    expect(json).toHaveAttribute('tabindex', '-1');
    expect(c.queryByLabelText('Wynik konwersji w formacie JSON')).toBeNull();

    // Answers survive leaving the preview tab.
    const input = (c.getAllByRole('textbox') as HTMLInputElement[]).find((t) => !t.readOnly && !t.disabled)!;
    await userEvent.clear(input);
    await userEvent.type(input, 'Jan');
    expect(input.value).toBe('Jan');

    preview.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(json).toHaveAttribute('aria-selected', 'true');
    expect(json).toHaveFocus();
    expect(await c.findByRole('region', { name: 'Wynik konwersji w formacie JSON' })).toBe(jsonRegion(c));
    expect(jsonRegion(c).tagName).toBe('PRE');
    expect(jsonRegion(c).textContent).toBe(JSON.stringify(nadplata, null, 2));
    expect(c.getByRole('heading', { level: 2, name: nadplata.title, hidden: true })).not.toBeVisible();
    await userEvent.keyboard('{ArrowRight}');
    expect(report).toHaveAttribute('aria-selected', 'true');
    expect(report).toHaveFocus();
    expect(c.getByText('Raport niedostępny dla tego wyniku.')).toBeVisible();
    await userEvent.keyboard('{End}');
    expect(edit).toHaveAttribute('aria-selected', 'true');
    expect(edit).toHaveFocus();
    await userEvent.keyboard('{Home}');
    expect(preview).toHaveAttribute('aria-selected', 'true');
    expect(preview).toHaveFocus();
    expect(input.value).toBe('Jan');
    await userEvent.keyboard('{ArrowLeft}');
    expect(edit).toHaveAttribute('aria-selected', 'true');
    expect(edit).toHaveFocus();
    await userEvent.click(preview);
    expect(c.getByRole('heading', { level: 2, name: nadplata.title })).toBeVisible();
    expect(input).toBeVisible();
    expect(input.value).toBe('Jan');

    expect(c.getByRole('button', { name: 'Pobierz .json' })).toBeVisible();
    const validator = new URL((c.getByRole('link', { name: 'Sprawdź w walidatorze' }) as HTMLAnchorElement).href);
    expect(validator.pathname + validator.search).toBe('/validator?item=d1');
    expect(backPath(c, '← Wróć do importu')).toBe('/import');
  },
};

export const ZRaportem: Story = {
  args: { id: 'r1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const { ranges } = formatJson(nadplata);
    const expectHighlighted = (path: string) => {
      const fragment = c.getByLabelText(`Fragment JSON: ${path}`);
      expect(fragment).toHaveFocus();
      expect(fragment).toHaveClass('bg-warning-subtle');
      const { start, end } = ranges.get(path)!;
      const lines = [...fragment.querySelectorAll('[data-line]')].map((l) => Number(l.getAttribute('data-line')));
      expect(lines).toEqual(Array.from({ length: end - start + 1 }, (_, i) => start + i));
      expect(jsonRegion(c).querySelectorAll('.bg-warning-subtle')).toHaveLength(1);
    };

    const scroll = spyOn(Element.prototype, 'scrollIntoView');
    try {
      await userEvent.click(tab(c, 'Raport'));
      await userEvent.click(c.getByRole('button', { name: 'Pokaż w JSON: R12_DUPLICATE_TECH_NAME' }));
      expect(tab(c, 'JSON')).toHaveAttribute('aria-selected', 'true');
      await waitFor(() => expectHighlighted('tabs[1].questions[0].field.repeatingSectionGrid[1]'));
      // The first line of the range is centred, not the whole block.
      const first = c.getByLabelText('Fragment JSON: tabs[1].questions[0].field.repeatingSectionGrid[1]').querySelector('[data-line]');
      expect(scroll).toHaveBeenCalledWith({ block: 'center' });
      expect(scroll.mock.contexts.at(-1)).toBe(first);
    } finally {
      scroll.mockRestore();
    }
    expect(c.getByRole('group', { name: 'Fragment JSON: tabs[1].questions[0].field.repeatingSectionGrid[1]' })).toHaveFocus();

    // Leaving the JSON tab clears the highlight.
    await userEvent.click(tab(c, 'Podgląd formularza'));
    await userEvent.click(tab(c, 'JSON'));
    expect((await c.findByRole('region', { name: 'Wynik konwersji w formacie JSON' })).querySelector('.bg-warning-subtle')).toBeNull();

    await userEvent.click(tab(c, 'Raport'));
    await userEvent.click(c.getByRole('button', { name: 'Pokaż w JSON: R12_DUPLICATE_TECH_NAME' }));
    // Ends with the highlight on screen so the a11y scan checks the fragment too.
    await waitFor(() => expectHighlighted('tabs[1].questions[0].field.repeatingSectionGrid[1]'));
  },
};

export const NotAForm: Story = {
  args: { id: 'n1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByText(previewMessage)).toBeVisible();
    expect(c.queryByRole('tab', { name: 'Podgląd formularza' })).toBeNull();
    expect(tab(c, 'JSON')).toHaveAttribute('aria-selected', 'true');
    expect(jsonRegion(c).textContent).toBe(JSON.stringify({ foo: 1 }, null, 2));
    await userEvent.click(tab(c, 'Raport'));
    expect(c.getByText('Raport niedostępny dla tego wyniku.')).toBeVisible();
    expect(c.getByRole('button', { name: 'Pobierz .json' })).toBeVisible();
  },
};

export const Unavailable: Story = {
  args: { id: 'nieznane' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(
      c.getByText('Wynik niedostępny. Wróć do importu i przetwórz plik ponownie.'),
    ).toBeVisible();
    expect(c.queryByRole('button', { name: 'Pobierz .json' })).toBeNull();
    expect(backPath(c, '← Wróć do importu')).toBe('/import');
  },
};

/** Field editor tab; the MockStore ignores edits, so this shows the controls (and runs the a11y scan on them). */
export const Edycja: Story = {
  args: { id: 'd1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await userEvent.click(tab(c, 'Edycja'));
    expect(c.getByRole('heading', { level: 2, name: `Strona 1: ${nadplata.tabs[0].title}` })).toBeVisible();
    await userEvent.click(c.getByRole('button', { name: 'Dodaj pole w sekcji Dane podmiotu' }));
    expect(c.getByRole('group', { name: 'Nowe pole w sekcji „Dane podmiotu”' })).toBeVisible();
  },
};
