import { Component, input, signal } from '@angular/core';

let nextId = 0;

// Disclosure: p-1 -m-1 gives a 24px target without moving the icon; the panel sits in the host's flex-wrap row (label row of the field), on its own line.
@Component({
  selector: 'app-field-tooltip',
  template: `
    <button
      type="button"
      class="inline-flex p-1 -m-1 rounded-full text-fg-muted focus-ring"
      [attr.aria-label]="'Więcej informacji: ' + label()"
      [attr.aria-expanded]="expanded()"
      [attr.aria-controls]="panelId"
      (click)="expanded.set(!expanded())"
      (keydown.escape)="expanded.set(false)"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        class="size-4"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <circle cx="8" cy="8" r="6.5" />
        <path d="M8 7.25v4M8 4.75v.5" stroke-linecap="round" />
      </svg>
    </button>
    <!-- Always present live region: the help text is announced when it appears. -->
    <div class="order-last basis-full text-fg-muted" aria-live="polite" [id]="panelId">
      @if (expanded()) {
        <div [innerHTML]="text()"></div>
      }
    </div>
  `,
  host: { class: 'contents' },
})
export class FieldTooltip {
  readonly text = input.required<string>();
  readonly label = input.required<string>();

  protected readonly expanded = signal(false);
  protected readonly panelId = `app-field-tooltip-${nextId++}`;
}
