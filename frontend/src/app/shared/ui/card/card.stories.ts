import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';
import { Button } from '../button/button';
import { Card } from './card';

@Component({
  selector: 'app-card-harness',
  imports: [Card, Button],
  template: `
    <app-card>
      <h2 cardTitle>Kolejka</h2>
      <button appButton cardActions variant="primary">Pobierz wszystkie (ZIP)</button>
      <p>Treść</p>
    </app-card>
  `,
})
class CardHarness {}

const meta: Meta<CardHarness> = {
  title: 'UI/Card',
  component: CardHarness,
};
export default meta;
type Story = StoryObj<CardHarness>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const css = (el: Element) => getComputedStyle(el);
    const card = c.getByText('Treść').closest('app-card')!;
    expect(css(card).backgroundColor).toBe('rgb(255, 255, 255)');
    expect(css(card).borderRadius).toBe('6px');
    expect(
      c.getByRole('heading', { name: 'Kolejka' }).compareDocumentPosition(c.getByRole('button')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  },
};

export const Preview: Story = {
  globals: { theme: 'preview' },
  play: async ({ canvasElement }) => {
    const card = within(canvasElement).getByText('Treść').closest('app-card')!;
    expect(getComputedStyle(card).borderRadius).toBe('8px');
  },
};
