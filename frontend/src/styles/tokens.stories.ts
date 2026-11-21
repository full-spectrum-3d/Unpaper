import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, within } from 'storybook/test';

@Component({
  selector: 'app-tokens-harness',
  template: `
  <div class="grid grid-cols-2">
    @for (t of themes; track t) {
      <div [attr.data-theme]="t === 'preview' ? 'preview' : null" [attr.data-testid]="t">
        <div data-testid="page" class="bg-bg p-4">
          <div data-testid="body" class="bg-surface text-fg text-body">
            Zażółć gęślą jaźń
            <button data-testid="btn" class="focus-ring">Przycisk</button>
            <div data-testid="raw" class="bg-red-500">raw</div>
          </div>
        </div>
      </div>
    }
  </div>`,
})
class TokensHarness {
  readonly themes = ['tool', 'preview'];
}

const meta: Meta = { title: 'Fundamenty/Tokeny (test)', component: TokensHarness };
export default meta;

export const Tokens: StoryObj = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const tool = within(c.getByTestId('tool'));
    const preview = within(c.getByTestId('preview'));
    const css = (el: HTMLElement) => getComputedStyle(el);

    // nested preview overrides only its subtree
    expect(css(tool.getByTestId('body')).fontSize).toBe('13px');
    expect(css(preview.getByTestId('body')).fontSize).toBe('15px');
    expect(css(tool.getByTestId('page')).backgroundColor).toBe('rgb(247, 248, 250)');
    expect(css(preview.getByTestId('page')).backgroundColor).toBe('rgb(242, 245, 249)');
    expect(css(tool.getByTestId('body')).color).toBe('rgb(31, 35, 40)');
    // default palette is disabled
    expect(css(tool.getByTestId('raw')).backgroundColor).toBe('rgba(0, 0, 0, 0)');
    // fonts.check() is true even without the font, so assert load() found a FontFace
    const faces = await document.fonts.load('15px "Open Sans"', 'ąęłżźćńóś');
    expect(faces.length).toBeGreaterThan(0);
    // focus ring is a 3px solid outline
    await userEvent.tab();
    const s = css(tool.getByTestId('btn'));
    expect([s.outlineStyle, s.outlineWidth, s.outlineOffset]).toEqual(['solid', '3px', '2px']);
    expect(s.outlineColor).toBe('rgb(0, 82, 165)');
  },
};
