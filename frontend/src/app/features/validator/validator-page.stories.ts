import { provideRouter } from '@angular/router';
import { provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { of } from 'rxjs';
import { expect, userEvent, waitFor, within } from 'storybook/test';
import { FormsService } from '../../shared/api/services/forms.service';
import { importQueueFeatureKey } from '../../store/import-queue/import-queue.reducer';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { ValidatorPage } from './validator-page';

const withResponse = (response: object) =>
  applicationConfig({
    providers: [
      { provide: FormsService, useValue: { validateApiV1FormsValidatePost: () => of(response) } },
    ],
  });

const meta: Meta<ValidatorPage> = {
  title: 'Ekrany/Walidator',
  component: ValidatorPage,
  decorators: [
    applicationConfig({
      providers: [
        provideRouter([]),
        provideMockStore({ initialState: { [importQueueFeatureKey]: { ids: [], entities: {} } } }),
      ],
    }),
  ],
};
export default meta;
type Story = StoryObj<ValidatorPage>;

const fill = async (c: ReturnType<typeof within>, text: string) => {
  await userEvent.click(c.getByLabelText('JSON formularza'));
  await userEvent.paste(text);
};

export const Pusty: Story = {
  decorators: [withResponse({ valid: true, errors: [], warnings: [] })],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByRole('heading', { level: 1, name: 'Walidator JSON' })).toBeVisible();
    expect(c.getByRole('button', { name: 'Sprawdź' })).toBeDisabled();
    expect(c.getByRole('button', { name: 'Wgraj plik .json' })).toBeEnabled();
  },
};

export const ZBledami: Story = {
  decorators: [
    withResponse({
      valid: false,
      errors: [
        { code: 'R06_REQUIREDNESS', message: 'Pole wymagane bez etykiety.', path: 'tabs[0]' },
        { code: 'R01_SCHEMA', message: 'Niezgodność ze schematem.', path: 'nie.ma' },
      ],
      warnings: [{ code: 'W02_LABEL_TOO_LONG', message: 'Etykieta jest zbyt długa.' }],
    }),
  ],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await fill(c, JSON.stringify(nadplata, null, 2));
    await userEvent.click(c.getByRole('button', { name: 'Sprawdź' }));
    expect(await c.findByRole('status')).toHaveTextContent('Znaleziono 2 błędy i 1 ostrzeżenie.');
    await waitFor(() => expect(c.getByRole('heading', { level: 2, name: 'Wynik' })).toHaveFocus());
    expect(c.getByRole('heading', { level: 3, name: 'Błędy (2)' })).toBeVisible();
    expect(c.getByRole('heading', { level: 3, name: 'Ostrzeżenia (1)' })).toBeVisible();
    expect(c.queryByRole('button', { name: 'Pokaż w JSON: R01_SCHEMA' })).toBeNull();
    await userEvent.click(c.getByRole('button', { name: 'Pokaż w JSON: R06_REQUIREDNESS' }));
    await waitFor(() =>
      expect(c.getByRole('group', { name: 'Fragment JSON: tabs[0]' })).toHaveFocus(),
    );
  },
};

export const Poprawny: Story = {
  decorators: [withResponse({ valid: true, errors: [], warnings: [] })],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await fill(c, JSON.stringify(nadplata, null, 2));
    await userEvent.click(c.getByRole('button', { name: 'Sprawdź' }));
    expect(await c.findByRole('status')).toHaveTextContent('JSON spełnia reguły COI.');
    expect(c.getByLabelText('Sprawdzany JSON').textContent).toBe(JSON.stringify(nadplata, null, 2));
    await userEvent.type(c.getByLabelText('JSON formularza'), ' ');
    expect(c.getByText('JSON zmieniono po sprawdzeniu. Sprawdź ponownie.')).toBeVisible();
  },
};

export const BladSkladni: Story = {
  decorators: [withResponse({ valid: true, errors: [], warnings: [] })],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await fill(c, '{\n  "title": "A",\n  "tabs": [\n}');
    await userEvent.click(c.getByRole('button', { name: 'Sprawdź' }));
    const field = c.getByLabelText('JSON formularza');
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(field).toHaveAccessibleDescription(/^Niepoprawny JSON/);
    expect(field).toHaveFocus();
    expect(c.queryByRole('heading', { name: 'Wynik' })).toBeNull();
  },
};
