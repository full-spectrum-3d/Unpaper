import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';
import { Progress } from './progress';

@Component({
  selector: 'app-progress-harness',
  imports: [Progress],
  template: `<app-progress label="Przetwarzanie wniosek.pdf" />`,
})
class ProgressHarness {}

const meta: Meta<ProgressHarness> = {
  title: 'UI/Progress',
  component: ProgressHarness,
};
export default meta;
type Story = StoryObj<ProgressHarness>;

export const Indeterminate: Story = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const bar = c.getByRole('progressbar', { name: 'Przetwarzanie wniosek.pdf' });
    expect(bar.hasAttribute('aria-valuenow')).toBe(false);
    expect(getComputedStyle(bar).backgroundColor).toBe('rgb(234, 242, 251)');
  },
};

export const Preview: Story = { ...Indeterminate, globals: { theme: 'preview' } };
