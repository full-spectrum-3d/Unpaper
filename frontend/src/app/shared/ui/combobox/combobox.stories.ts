import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, within } from 'storybook/test';
import { findDictionary } from '../../../features/preview/dictionaries.mock';
import { Combobox } from './combobox';

const countries = findDictionary('Kraje')!.items.map((n) => n.name);

const meta: Meta<Combobox> = {
  title: 'UI/Combobox',
  component: Combobox,
  args: { label: 'Kraj', options: ['Polska', 'Niemcy', 'Norwegia'] },
};
export default meta;
type Story = StoryObj<Combobox>;

export const Domyślny: Story = {};

export const ZWartością: Story = { args: { value: 'Polska' } };

export const Wyszukiwanie: Story = {
  args: { options: countries, searchable: true },
  play: async ({ canvasElement }) => {
    const input = within(canvasElement).getByRole('combobox', { name: 'Kraj' });
    await userEvent.type(input, 'pol');
    await userEvent.keyboard('{Enter}');
    await expect(input).toHaveValue('Polska');
  },
};

export const PustaLista: Story = {
  args: { label: 'Gatunek', options: [], emptyText: 'Brak pozycji w słowniku X' },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await userEvent.click(c.getByRole('combobox', { name: 'Gatunek' }));
    await expect(c.getByRole('status')).toHaveTextContent('Brak pozycji w słowniku X');
    const [, visible] = c.getAllByText('Brak pozycji w słowniku X');
    await expect(visible).toBeVisible();
  },
};
