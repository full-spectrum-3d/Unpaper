import { Component, computed, input } from '@angular/core';
import { FieldTooltip } from '../../../shared/ui/field-tooltip/field-tooltip';

/**
 * Label row like app-text-field's: label (with sr-only tag and required marker), tooltip disclosure, visible tag.
 * The asterisk sits outside the label, visual only: controls carry aria-required.
 * Groups that cannot (role=group, labelled by the span) set announceRequired to put it into their name.
 */
@Component({
  selector: 'app-field-label',
  imports: [FieldTooltip],
  template: `
    <div [class]="hidden() ? 'contents' : 'flex flex-wrap items-center gap-x-2 mb-1.5'">
      @if (for(); as target) {
        <label [id]="labelId()" [for]="target" [class]="labelClass()"
          >{{ label() }}<span class="sr-only">{{ tag() ? ', ' + tag() : '' }}</span></label
        >
      } @else {
        <span [id]="labelId()" [class]="labelClass()"
          >{{ label() }}<span class="sr-only">{{ tag() ? ', ' + tag() : '' }}</span>
          @if (required() && announceRequired()) {
            <span class="sr-only"> (wymagane)</span>
          }
        </span>
      }
      @if (required() && !hidden()) {
        <span class="text-danger -ml-1.5" aria-hidden="true">*</span>
      }
      @if (tooltip(); as text) {
        <app-field-tooltip [text]="text" [label]="label()" />
      }
      @if (tag(); as text) {
        <span class="ml-auto text-fg-muted text-label font-normal" aria-hidden="true">{{
          text
        }}</span>
      }
    </div>
  `,
  host: { class: 'block' },
})
export class FieldLabel {
  readonly label = input.required<string>();
  /** Id of the labelled control; without it the label is a span for aria-labelledby. */
  readonly for = input<string>();
  readonly labelId = input<string>();
  readonly hidden = input(false);
  readonly tooltip = input<string>();
  readonly tag = input<string>();
  readonly required = input(false);
  readonly announceRequired = input(false);
  protected readonly labelClass = computed(() =>
    this.hidden() ? 'sr-only' : 'text-label font-label',
  );
}
