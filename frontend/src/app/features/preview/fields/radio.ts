import { Component } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-radio-field',
  imports: [FieldLabel],
  template: `
    <!-- aria-labelledby instead of a legend: the label row also holds the tooltip button.
         role=radiogroup: unlike a plain group it supports aria-required and aria-readonly. -->
    <fieldset
      role="radiogroup"
      class="m-0 p-0 border-0"
      [attr.aria-labelledby]="id() + '-label'"
      [attr.aria-describedby]="describedBy()"
      [attr.aria-required]="required() || null"
      [attr.aria-readonly]="readOnly() || null"
    >
      <app-field-label
        [label]="label()"
        [labelId]="id() + '-label'"
        [hidden]="!hasTitle()"
        [tooltip]="tooltip()"
        [tag]="tag()"
        [required]="required()"
      />
      @if (hasDescription()) {
        <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
      }
      <!-- Options come from imported JSON: ids may repeat, so track by position. -->
      @for (o of field().options ?? []; track $index) {
        <label class="flex items-center gap-2 py-1">
          <input
            type="radio"
            class="focus-ring"
            [name]="field().id"
            [value]="o.name"
            [checked]="value() === o.name"
            [attr.aria-describedby]="describedBy()"
            [attr.aria-invalid]="error() ? 'true' : null"
            (click)="blockIfReadOnly($event)"
            (keydown)="blockArrows($event)"
            (change)="set(o.name)"
          />
          {{ o.name }}
        </label>
      }
      @if (error(); as text) {
        <small [id]="errorId()" class="block text-danger"
          ><span aria-hidden="true">✕</span> {{ text }}</small
        >
      }
    </fieldset>
  `,
  host: { class: 'block' },
})
export class RadioField extends FieldBase {
  /** Arrow keys move the checked radio natively; a read-only group keeps its choice. */
  protected blockArrows(event: KeyboardEvent) {
    if (event.key.startsWith('Arrow')) this.blockIfReadOnly(event);
  }
}
