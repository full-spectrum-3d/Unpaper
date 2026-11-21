import { Component, output } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, within } from 'storybook/test';
import { Button } from './button';

@Component({
  selector: 'app-button-harness',
  imports: [Button],
  template: `
    <button appButton variant="primary">Zapisz</button>
    <button appButton>Anuluj</button>
    <button appButton variant="ghost">Usuń</button>
    <button appButton disabled (click)="clicked.emit()">Wyłączony</button>
  `,
})
class ButtonHarness {
  readonly clicked = output();
}

const meta: Meta<ButtonHarness> = {
  title: 'UI/Button',
  component: ButtonHarness,
  args: { clicked: fn() },
};
export default meta;
type Story = StoryObj<ButtonHarness>;

export const Variants: Story = {
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    const css = (el: HTMLElement) => getComputedStyle(el);
    const save = c.getByRole('button', { name: 'Zapisz' });
    expect(css(save).backgroundColor).toBe('rgb(0, 82, 165)');
    expect(css(save).color).toBe('rgb(255, 255, 255)');
    expect(css(c.getByRole('button', { name: 'Anuluj' })).backgroundColor).toBe(
      'rgb(255, 255, 255)',
    );
    expect(css(c.getByRole('button', { name: 'Anuluj' })).borderColor).toBe('rgb(0, 82, 165)');
    expect(css(c.getByRole('button', { name: 'Usuń' })).backgroundColor).toBe('rgba(0, 0, 0, 0)');
    expect(css(save).borderRadius).toBe('4px');
    // disabled button does not fire click
    await userEvent.click(c.getByRole('button', { name: 'Wyłączony' }), { pointerEventsCheck: 0 });
    expect(args.clicked).not.toHaveBeenCalled();
    // focus ring
    await userEvent.tab();
    expect(css(document.activeElement as HTMLElement).outlineWidth).toBe('3px');
  },
};

export const Preview: Story = { ...Variants, globals: { theme: 'preview' } };
