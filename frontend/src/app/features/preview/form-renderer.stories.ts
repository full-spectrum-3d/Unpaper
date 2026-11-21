import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, waitFor, within } from 'storybook/test';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import numerPorzadkowy from '../import/mock-forms/numer-porzadkowy.json';
import { FormDefinition } from './form-definition';
import { FormRenderer } from './form-renderer';

const meta: Meta<FormRenderer> = {
  title: 'Ekrany/Podgląd formularza',
  component: FormRenderer,
  globals: { theme: 'preview' },
};
export default meta;
type Story = StoryObj<FormRenderer>;

export const Nadplata: Story = {
  args: { definition: nadplata as unknown as FormDefinition },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const heading = (level: number, name: string) => c.findByRole('heading', { level, name });
    await heading(2, 'Wniosek o stwierdzenie nadpłaty podatku');
    const step1 = await heading(3, 'Krok 1 z 3: Dane');
    expect(step1).toHaveAttribute('tabindex', '-1');
    expect(c.getByDisplayValue('Urząd Gminy Ulan-Majorat')).toHaveAttribute('readonly');
    expect(c.queryByRole('heading', { name: 'Dane innej osoby' })).toBeNull();
    expect(c.queryByRole('button', { name: 'Wstecz' })).toBeNull();

    await userEvent.click(c.getByRole('radio', { name: 'Innej osoby' }));
    await heading(4, 'Dane innej osoby');

    const budynek = c.getAllByRole('textbox', { name: 'Numer budynku' })[0];
    const initial = (budynek as HTMLInputElement).value; // may be prefilled from the registry
    await userEvent.type(budynek, 'X');

    await userEvent.click(c.getByRole('button', { name: 'Dalej' }));
    const step2 = await heading(3, 'Krok 2 z 3: Informacje o nadpłacie');
    await waitFor(() => expect(document.activeElement).toBe(step2));

    await userEvent.click(c.getByRole('button', { name: 'Wstecz' }));
    await heading(3, 'Krok 1 z 3: Dane');
    expect(c.getAllByRole('textbox', { name: 'Numer budynku' })[0]).toHaveValue(initial + 'X');

    await userEvent.click(c.getByRole('button', { name: 'Przerwij wypełnianie' }));
    await heading(3, 'Krok 1 z 3: Dane');
    await waitFor(() => expect(c.getAllByRole('textbox', { name: 'Numer budynku' })[0]).toHaveValue(initial));

    for (let i = 0; i < 3; i++) await userEvent.click(c.getByRole('button', { name: 'Dalej' }));
    await heading(3, 'Podsumowanie');
    expect(c.queryByRole('button', { name: 'Dalej' })).toBeNull();
  },
};

export const NumerPorzadkowy: Story = {
  args: { definition: numerPorzadkowy as unknown as FormDefinition },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await c.findByRole('heading', {
      level: 2,
      name: 'Wniosek o ustalenie numeru porządkowego nieruchomości',
    });
    await c.findByRole('heading', { level: 3, name: /^Krok 1 z 3/ });
  },
};
