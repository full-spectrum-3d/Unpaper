import { Component, output } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, within } from 'storybook/test';
import { Topbar } from './topbar';

@Component({
  selector: 'app-topbar-harness',
  imports: [Topbar],
  template: `
    <app-topbar appName="Cyfryzacja formularzy" userName="j.nowak" (logout)="logout.emit()">
      <a href="#" aria-current="page">Import</a>
      <a href="#">Walidator</a>
    </app-topbar>
  `,
})
class TopbarHarness {
  readonly logout = output();
}

const meta: Meta<TopbarHarness> = {
  title: 'UI/Topbar',
  component: TopbarHarness,
  args: { logout: fn() },
};
export default meta;
type Story = StoryObj<TopbarHarness>;

export const Default: Story = {
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    const header = c.getByRole('banner');
    expect(getComputedStyle(header).backgroundColor).toBe('rgb(20, 35, 60)');
    expect(within(c.getByRole('navigation', { name: 'Główna' })).getAllByRole('link')).toHaveLength(
      2,
    );
    expect(c.getByText('j.nowak')).toBeVisible();
    await userEvent.click(c.getByRole('button', { name: 'Wyloguj' }));
    expect(args.logout).toHaveBeenCalledOnce();
  },
};

export const Preview: Story = { ...Default, globals: { theme: 'preview' } };
