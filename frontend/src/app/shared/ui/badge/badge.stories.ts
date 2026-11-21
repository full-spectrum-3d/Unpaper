import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';
import { Badge } from './badge';

@Component({
  selector: 'app-badge-harness',
  imports: [Badge],
  template: `
    <app-badge status="pending" />
    <app-badge status="processing" />
    <app-badge status="done" />
    <app-badge status="error" />
  `,
})
class BadgeHarness {}

const meta: Meta<BadgeHarness> = {
  title: 'UI/Badge',
  component: BadgeHarness,
};
export default meta;
type Story = StoryObj<BadgeHarness>;

export const Statuses: Story = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const css = (el: Element) => getComputedStyle(el);
    // each status has visible text label
    for (const t of ['Oczekuje', 'Przetwarzanie', 'Gotowe', 'Błąd'])
      expect(c.getByText(t)).toBeVisible();
    const done = c.getByText('Gotowe').closest('app-badge')!;
    expect(css(done).backgroundColor).toBe('rgb(230, 244, 234)');
    expect(css(done).color).toBe('rgb(19, 108, 46)');
    expect(css(c.getByText('Błąd').closest('app-badge')!).color).toBe('rgb(179, 38, 30)');
    expect(css(c.getByText('Oczekuje').closest('app-badge')!).color).toBe('rgb(122, 79, 0)');
    expect(css(c.getByText('Przetwarzanie').closest('app-badge')!).color).toBe('rgb(0, 82, 165)');
    expect(done.querySelector('[aria-hidden="true"]')).not.toBeNull();
  },
};

export const Preview: Story = { ...Statuses, globals: { theme: 'preview' } };
