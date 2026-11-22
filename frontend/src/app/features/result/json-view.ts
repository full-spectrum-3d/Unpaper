import { Component, ElementRef, Injector, afterNextRender, computed, inject, input, signal, viewChild } from '@angular/core';
import { JsonLines } from './json-lines';

@Component({
  selector: 'app-json-view',
  // Whitespace inside <pre> is significant: keep the content on one line.
  template: `<pre
    #region
    role="region"
    tabindex="0"
    [attr.aria-label]="label()"
    class="overflow-auto p-[10px] text-[13px] font-mono focus-ring"
  >@for (seg of segments(); track $index) {@if (seg.highlight) {<span #fragment role="group" tabindex="-1" class="block bg-warning-subtle focus-ring" [attr.aria-label]="'Fragment JSON: ' + highlight()">@for (l of seg.lines; track l.n) {<span [attr.data-line]="l.n">{{ l.text }}</span>}</span>} @else {@for (l of seg.lines; track l.n) {<span [attr.data-line]="l.n">{{ l.text }}</span>}}}</pre>
  <!-- Always rendered so it can fade in and out; hidden, it is inert for keyboard and screen readers. -->
  <button
    type="button"
    aria-label="Wróć na górę"
    [attr.data-visible]="showTop()"
    [attr.aria-hidden]="showTop() ? null : 'true'"
    [attr.tabindex]="showTop() ? null : -1"
    class="fixed bottom-[24px] left-1/2 z-10 flex h-[44px] w-[44px] -translate-x-1/2 items-center justify-center rounded-full bg-primary text-on-primary shadow-md transition-[opacity,translate,visibility] duration-300 hover:opacity-90 focus-ring motion-reduce:transition-none"
    [class]="showTop() ? 'opacity-100 translate-y-0 visible' : 'opacity-0 translate-y-[12px] invisible'"
    (click)="toTop()"
  >
    <svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  </button>`,
  host: { '(window:scroll)': 'onScroll()' },
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
  private readonly region = viewChild<ElementRef<HTMLElement>>('region');
  /** The reader has scrolled well past the top of the JSON, so a way back up is useful. */
  protected readonly showTop = signal(false);

  protected onScroll(): void {
    this.showTop.set(window.scrollY > 400);
  }

  protected toTop(): void {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    // The button disappears once the page is at the top: keep keyboard focus on the JSON.
    this.region()?.nativeElement.focus({ preventScroll: true });
  }

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
