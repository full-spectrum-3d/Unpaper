import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';

@Component({
  selector: 'app-theme-switch-harness',
  template: `<p class="text-body">Treść</p>`,
})
class ThemeSwitchHarness {}

const meta: Meta = { title: 'Fundamenty/Przełącznik motywu', component: ThemeSwitchHarness };
export default meta;

const check = (theme: string, fontSize: string): StoryObj['play'] => async ({ canvasElement }) => {
  const el = within(canvasElement).getByText('Treść');
  expect(el.closest('[data-theme]')?.getAttribute('data-theme')).toBe(theme);
  expect(getComputedStyle(el).fontSize).toBe(fontSize);
};

export const Tool: StoryObj = { play: check('tool', '13px') };
export const Preview: StoryObj = { globals: { theme: 'preview' }, play: check('preview', '15px') };
