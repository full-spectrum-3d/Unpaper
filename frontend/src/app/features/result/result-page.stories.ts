import { provideRouter } from '@angular/router';
import { provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';
import { QueueItem, importQueueFeatureKey } from '../../store/import-queue/import-queue.reducer';
import { ResultPage } from './result-page';

const done: QueueItem = {
  id: 'd1',
  name: 'Deklaracja o wysokości opłaty.docx',
  size: 84 * 1024,
  status: 'done',
  error: null,
  retryable: false,
  result: { title: 'Deklaracja o wysokości opłaty', fields: [{ name: 'imie', value: 'Jan' }] },
  startedAt: 0,
  durationMs: 12000,
};

const meta: Meta<ResultPage> = {
  title: 'Ekrany/Wynik',
  component: ResultPage,
  decorators: [
    applicationConfig({
      providers: [
        provideRouter([]),
        provideMockStore({
          initialState: {
            [importQueueFeatureKey]: { ids: [done.id], entities: { [done.id]: done } },
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

export const Done: Story = {
  args: { id: 'd1' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByRole('heading', { name: done.name })).toBeVisible();
    const pre = c.getByLabelText('Wynik konwersji w formacie JSON');
    expect(pre.tagName).toBe('PRE');
    expect(pre).toHaveAttribute('tabindex', '0');
    expect(pre.textContent).toContain('"title"');
    expect(c.getByRole('button', { name: 'Pobierz .json' })).toBeVisible();
    expect(backPath(c, '← Wróć do importu')).toBe('/import');
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
