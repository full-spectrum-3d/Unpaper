import { provideRouter } from '@angular/router';
import { provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, within } from 'storybook/test';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
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
  startedAt: 0,
  durationMs: 12000,
};

const notAForm: QueueItem = { ...done, id: 'n1', result: { foo: 1 } };

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
              ids: [done.id, notAForm.id],
              entities: { [done.id]: done, [notAForm.id]: notAForm },
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

export const Done: Story = {
  args: { id: 'd1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByRole('heading', { level: 1, name: done.name })).toBeVisible();
    const title = await c.findByRole('heading', { level: 2, name: nadplata.title });
    expect(title.closest('[data-theme="preview"]')).not.toBeNull();
    expect(title.closest('main')).not.toBeNull();
    expect(c.getByRole('group', { name: 'Widok wyniku' })).toBeVisible();
    expect(c.queryByText(previewMessage)).toBeNull();
    const previewBtn = c.getByRole('button', { name: 'Podgląd formularza' });
    const jsonBtn = c.getByRole('button', { name: 'JSON' });
    expect(previewBtn).toHaveAttribute('aria-pressed', 'true');
    expect(jsonBtn).toHaveAttribute('aria-pressed', 'false');
    expect(c.queryByLabelText('Wynik konwersji w formacie JSON')).toBeNull();

    await userEvent.click(jsonBtn);
    expect(jsonBtn).toHaveAttribute('aria-pressed', 'true');
    const pre = c.getByLabelText('Wynik konwersji w formacie JSON');
    expect(pre.tagName).toBe('PRE');
    expect(pre).toHaveAttribute('tabindex', '0');
    expect(pre.textContent).toContain('"title"');
    expect(c.getByRole('region', { name: 'Wynik konwersji w formacie JSON' })).toBe(pre);
    expect(
      c.getByRole('heading', { level: 2, name: nadplata.title, hidden: true }),
    ).not.toBeVisible();
    expect(c.getByRole('button', { name: 'Pobierz .json' })).toBeVisible();
    expect(backPath(c, '← Wróć do importu')).toBe('/import');

    await userEvent.click(previewBtn);
    expect(previewBtn).toHaveAttribute('aria-pressed', 'true');
    expect(c.getByRole('heading', { level: 2, name: nadplata.title })).toBeVisible();
    expect(pre).not.toBeVisible();
  },
};

export const NotAForm: Story = {
  args: { id: 'n1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByText(previewMessage)).toBeVisible();
    expect(c.queryByRole('button', { name: 'Podgląd formularza' })).toBeNull();
    expect(c.getByLabelText('Wynik konwersji w formacie JSON').textContent).toContain('"foo"');
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
