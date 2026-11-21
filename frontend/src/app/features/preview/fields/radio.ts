import { Component } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-radio-field',
  imports: [FieldLabel],
  template: `
    <!-- aria-labelledby instead of a legend: the label row also holds the tooltip button. -->
    <fieldset
      class="m-0 p-0 border-0"
      [attr.aria-labelledby]="id() + '-label'"
      [attr.aria-describedby]="describedBy()"
    >
      <app-field-label
        [label]="label()"
        [labelId]="id() + '-label'"
        [hidden]="!hasTitle()"
        [tooltip]="tooltip()"
        [tag]="tag()"
      />
      @if (hasDescription()) {
        <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
      }
      @for (o of field().options ?? []; track o.id) {
        <label class="flex items-center gap-2 py-1">
          <input
            type="radio"
            class="focus-ring"
            [name]="field().id"
            [value]="o.name"
            [checked]="value() === o.name"
            [disabled]="readOnly()"
            [attr.aria-invalid]="error() ? 'true' : null"
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
export class RadioField extends FieldBase {}
