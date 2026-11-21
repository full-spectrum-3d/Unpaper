import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, within } from 'storybook/test';
import { FieldTooltip } from './field-tooltip';

const meta: Meta<FieldTooltip> = {
  title: 'UI/FieldTooltip',
  component: FieldTooltip,
  args: { label: 'Numer PESEL', text: 'Jedenaście cyfr, bez spacji.' },
};
export default meta;
type Story = StoryObj<FieldTooltip>;

export const Zwinięty: Story = {};

export const Rozwinięty: Story = {
  play: async ({ canvasElement }) => {
    const button = within(canvasElement).getByRole('button', {
      name: 'Więcej informacji: Numer PESEL',
    });
    await userEvent.click(button);
    await expect(button).toHaveAttribute('aria-expanded', 'true');
    await expect(within(canvasElement).getByText('Jedenaście cyfr, bez spacji.')).toBeVisible();
  },
};
