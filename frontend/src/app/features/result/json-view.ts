import { Component, ElementRef, Injector, afterNextRender, computed, inject, input, viewChild } from '@angular/core';
import { JsonLines } from './json-lines';

@Component({
  selector: 'app-json-view',
  // Whitespace inside <pre> is significant: keep the content on one line.
  template: `<pre
    role="region"
    tabindex="0"
    [attr.aria-label]="label()"
    class="overflow-auto p-[10px] text-[13px] font-mono focus-ring"
  >@for (seg of segments(); track $index) {@if (seg.highlight) {<span #fragment role="group" tabindex="-1" class="block bg-warning-subtle focus-ring" [attr.aria-label]="'Fragment JSON: ' + highlight()">@for (l of seg.lines; track l.n) {<span [attr.data-line]="l.n">{{ l.text }}</span>}</span>} @else {@for (l of seg.lines; track l.n) {<span [attr.data-line]="l.n">{{ l.text }}</span>}}}</pre>`,
})
export class JsonView {
  private readonly injector = inject(Injector);

  readonly lines = input.required<JsonLines>();
  readonly highlight = input<string | null>(null);
  readonly label = input.required<string>();

  /** JSON lines split into plain runs and the one highlighted range; newlines kept so textContent stays exact. */
  protected readonly segments = computed(() => {
    const { lines, ranges } = this.lines();
    const path = this.highlight();
    const range = path === null ? undefined : ranges.get(path);
    const cuts = range ? [0, range.start, range.end + 1, lines.length] : [0, lines.length];
    return cuts.slice(1).map((end, i) => ({
      highlight: !!range && i === 1,
      lines: lines
        .slice(cuts[i], end)
        .map((text, j) => ({ n: cuts[i] + j, text: cuts[i] + j < lines.length - 1 ? text + '\n' : text })),
    }));
  });
  private readonly fragment = viewChild<ElementRef<HTMLElement>>('fragment');

  /** Call after setting `highlight`: scrolls to the range and focuses it once rendered. */
  reveal(): void {
    afterNextRender(
      () => {
        const el = this.fragment()?.nativeElement;
        // Centre the first line, not the block: a tall range would push its start off-screen.
        el?.querySelector('[data-line]')?.scrollIntoView?.({ block: 'center' });
        el?.focus({ preventScroll: true });
      },
      { injector: this.injector },
    );
  }
}
