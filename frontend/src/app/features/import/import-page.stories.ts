import { inject, provideEnvironmentInitializer } from '@angular/core';
import { provideRouter } from '@angular/router';
import { ActionsSubject } from '@ngrx/store';
import { MockStore, provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';
import { ImportQueueActions } from '../../store/import-queue/import-queue.actions';
import {
  QueueItem,
  importQueueFeatureKey,
} from '../../store/import-queue/import-queue.reducer';
import { FileRegistry } from './file-registry';
import { ImportPage } from './import-page';

const dispatched = fn();
const registry = { add: fn(), get: fn(), delete: fn(), setPassword: fn() };
let mockStore: MockStore;

const stateOf = (items: QueueItem[]) => ({
  [importQueueFeatureKey]: {
    ids: items.map((i) => i.id),
    entities: Object.fromEntries(items.map((i) => [i.id, i])),
  },
});

const item = (p: Partial<QueueItem> & Pick<QueueItem, 'id' | 'name'>): QueueItem => ({
  size: 84 * 1024,
  status: 'pending',
  error: null,
  retryable: false,
  result: null,
  report: null,
  startedAt: null,
  durationMs: null,
  ...p,
});

function withQueue(items: QueueItem[]) {
  return applicationConfig({
    providers: [
      provideRouter([]),
      provideMockStore({ initialState: stateOf(items) }),
      provideEnvironmentInitializer(() => {
        mockStore = inject(MockStore);
      }),
      {
        provide: ActionsSubject,
        useFactory: () => {
          const s = new ActionsSubject();
          s.subscribe((a) => dispatched(a));
          return s;
        },
      },
      { provide: FileRegistry, useValue: registry },
    ],
  });
}

const mixed = [
  item({ id: 'd1', name: 'Deklaracja o wysokości opłaty.docx', status: 'done', result: {}, durationMs: 12000 }),
  item({ id: 'p1', name: 'Wniosek o dowód.pdf', size: 1.2 * 1024 * 1024, status: 'processing' }),
  item({ id: 'w1', name: 'Skan wniosku.jpg', status: 'pending' }),
  item({
    id: 'e1',
    name: 'formularz.jpe',
    status: 'error',
    error: 'Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.',
  }),
];

const meta: Meta<ImportPage> = {
  title: 'Ekrany/Import',
  component: ImportPage,
  beforeEach: () => {
    dispatched.mockClear();
  },
};
export default meta;
type Story = StoryObj<ImportPage>;

export const Empty: Story = {
  decorators: [withQueue([])],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByText('Kolejka jest pusta. Dodaj pliki powyżej.')).toBeVisible();
    expect(c.getByRole('button', { name: 'Pobierz wszystkie (ZIP)' })).toBeDisabled();
  },
};

export const Mixed: Story = {
  decorators: [withQueue(mixed)],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByText('4 pliki · 1 gotowy · 1 błąd')).toBeVisible();
    const heading = c.getByRole('heading', { name: 'Kolejka' });
    expect(c.getByRole('table')).toHaveAttribute('aria-labelledby', heading.id);
    expect(c.getByText('12 s')).toBeVisible();
    const open = c.getByRole('link', { name: 'Otwórz wynik Deklaracja o wysokości opłaty.docx' });
    expect(new URL((open as HTMLAnchorElement).href).pathname).toBe('/result/d1');
    expect(c.queryByRole('button', { name: /^Ponów/ })).toBeNull();
    expect(c.getByRole('button', { name: 'Usuń formularz.jpe' })).toHaveAccessibleDescription(
      /Nieobsługiwane/,
    );
    await userEvent.click(c.getByRole('button', { name: 'Usuń formularz.jpe' }));
    expect(dispatched).toHaveBeenCalledWith(ImportQueueActions.removed({ id: 'e1' }));
    const card = c.getByRole('table').closest('app-card') as HTMLElement;
    expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth);
  },
};

export const AnnouncesEveryChange: Story = {
  decorators: [withQueue([])],
  play: async ({ canvasElement }) => {
    const region = canvasElement.querySelector('[aria-live=polite]')!;
    const text = () => region.textContent ?? '';
    const bad = (n: string) => item({ id: n, name: `${n}.exe`, status: 'error', error: 'Zły typ' });
    // three invalid files arriving at once: nothing is lost
    mockStore.setState(stateOf([bad('a'), bad('b'), bad('c')]));
    await waitFor(() => {
      for (const n of ['a', 'b', 'c']) expect(text()).toContain(`${n}.exe: błąd – Zły typ`);
    });
    // the same error twice in a row still changes the text
    const first = text();
    mockStore.setState(stateOf([bad('a'), bad('b'), bad('c'), bad('d')]));
    await waitFor(() => expect(text()).not.toBe(first));
    const second = text();
    mockStore.setState(stateOf([bad('a'), bad('b'), bad('c'), bad('d'), bad('e')]));
    await waitFor(() => expect(text()).not.toBe(second));
  },
};

export const RetryableError: Story = {
  decorators: [
    withQueue([item({ id: 'r1', name: 'wniosek.pdf', status: 'error', error: 'Błąd serwera', retryable: true })]),
  ],
  play: async ({ canvasElement }) => {
    await userEvent.click(within(canvasElement).getByRole('button', { name: 'Ponów wniosek.pdf' }));
    expect(dispatched).toHaveBeenCalledWith(ImportQueueActions.retry({ id: 'r1' }));
  },
};

export const PasswordRequired: Story = {
  decorators: [
    withQueue([
      item({
        id: 'h1',
        name: 'umowa.pdf',
        status: 'error',
        error: 'Dokument jest zabezpieczony hasłem. Podaj hasło, aby go przetworzyć.',
        retryable: true,
        passwordState: 'required',
      }),
    ]),
  ],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    registry.setPassword.mockClear();
    expect(c.queryByRole('button', { name: 'Ponów umowa.pdf' })).toBeNull();
    const field = c.getByLabelText('Hasło do umowa.pdf');
    expect(field).toHaveAttribute('type', 'password');
    expect(field).toHaveAccessibleDescription(/zabezpieczony hasłem/);
    await userEvent.click(c.getByRole('button', { name: 'Odblokuj umowa.pdf' }));
    expect(dispatched).not.toHaveBeenCalledWith(ImportQueueActions.passwordSubmitted({ id: 'h1' }));
    expect(field).toHaveAccessibleDescription(/Wpisz hasło\./);
    expect(field).toHaveFocus();
    await userEvent.type(field, 'ą'.repeat(513));
    await userEvent.click(c.getByRole('button', { name: 'Odblokuj umowa.pdf' }));
    expect(field).toHaveAccessibleDescription(/Hasło jest za długie/);
    expect(registry.setPassword).not.toHaveBeenCalled();
    await userEvent.clear(field);
    await userEvent.type(field, 'tajne{Enter}');
    expect(registry.setPassword).toHaveBeenCalledWith('h1', 'tajne');
    expect(dispatched).toHaveBeenCalledWith(ImportQueueActions.passwordSubmitted({ id: 'h1' }));
    expect(field).toHaveValue('');
    // The store re-queues the file, the backend rejects the password: its field gets focus again.
    const row = (p: Partial<QueueItem>) => item({ id: 'h1', name: 'umowa.pdf', retryable: true, ...p });
    mockStore.setState(stateOf([row({ status: 'processing' })]));
    await waitFor(() => expect(c.queryByLabelText('Hasło do umowa.pdf')).toBeNull());
    mockStore.setState(
      stateOf([row({ status: 'error', error: 'Hasło jest niepoprawne. Spróbuj ponownie.', passwordState: 'invalid' })]),
    );
    await waitFor(() => expect(c.getByLabelText('Hasło do umowa.pdf')).toHaveFocus());
  },
};

export const PasswordInvalid: Story = {
  decorators: [
    withQueue([
      item({
        id: 'h2',
        name: 'umowa.pdf',
        status: 'error',
        error: 'Hasło jest niepoprawne. Spróbuj ponownie.',
        retryable: true,
        passwordState: 'invalid',
      }),
    ]),
  ],
  play: async ({ canvasElement }) => {
    expect(within(canvasElement).getByLabelText('Hasło do umowa.pdf')).toHaveAttribute('aria-invalid', 'true');
  },
};

export const LongName: Story = {
  decorators: [
    withQueue([
      item({ id: 'l1', name: 'formularz_z_bardzo_dluga_nazwa_bez_spacji_0123456789_0123456789_0123456789_0123456789.pdf' }),
    ]),
  ],
  play: async ({ canvasElement }) => {
    const card = within(canvasElement).getByRole('table').closest('app-card') as HTMLElement;
    expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth);
  },
};

export const AddFiles: Story = {
  decorators: [withQueue([])],
  play: async ({ canvasElement }) => {
    const input = canvasElement.querySelector<HTMLInputElement>('input[type=file]')!;
    await userEvent.upload(input, [
      new File(['x'], 'a.pdf', { type: 'application/pdf' }),
      new File(['x'], 'a.exe'),
    ], { applyAccept: false });
    await waitFor(() => expect(dispatched).toHaveBeenCalled());
    const action = dispatched.mock.calls.find((c) => c[0].type === ImportQueueActions.filesAdded.type)![0];
    expect(action.items).toHaveLength(2);
    expect(action.items[0].status).toBe('pending');
    expect(action.items[1]).toEqual(expect.objectContaining({ status: 'error', retryable: false }));
  },
};

export const Preview: Story = {
  ...Mixed,
  globals: { theme: 'preview' },
};
