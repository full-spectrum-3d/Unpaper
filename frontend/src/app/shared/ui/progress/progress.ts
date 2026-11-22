import { Component, computed, input } from '@angular/core';

@Component({
  selector: 'app-progress',
  template: `
    @if (value() === undefined) {
      <div class="bar h-full w-1/3 rounded-full bg-primary"></div>
    } @else {
      <div
        class="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none"
        [style.width.%]="clamped()"
      ></div>
    }
  `,
  styles: `
    @keyframes slide {
      from {
        transform: translateX(-100%);
      }
      to {
        transform: translateX(300%);
      }
    }
    .bar {
      animation: slide 1.2s ease-in-out infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      .bar {
        animation: none;
      }
    }
  `,
  host: {
    role: 'progressbar',
    '[attr.aria-label]': 'label()',
    // Determinate only when a value is given; otherwise the bar is indeterminate (no aria-valuenow).
    '[attr.aria-valuemin]': 'value() === undefined ? null : 0',
    '[attr.aria-valuemax]': 'value() === undefined ? null : 100',
    '[attr.aria-valuenow]': 'value() === undefined ? null : clamped()',
    '[attr.aria-valuetext]': 'valueText() ?? null',
    class: 'block h-[4px] overflow-hidden rounded-full bg-primary-subtle',
  },
})
export class Progress {
  readonly label = input.required<string>();
  /** Percent done, 0-100; omit for an indeterminate bar. */
  readonly value = input<number>();
  /** Spoken instead of the bare percent, e.g. "Krok 2 z 3". */
  readonly valueText = input<string>();
  protected readonly clamped = computed(() =>
    Math.round(Math.min(100, Math.max(0, this.value() ?? 0))),
  );
}
