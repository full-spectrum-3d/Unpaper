import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-radio-field',
  template: `
    <fieldset class="m-0 p-0 border-0" [attr.aria-describedby]="describedBy()">
      <legend [class]="labelClass()">{{ label() }}</legend>
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
            (change)="set(o.name)"
          />
          {{ o.name }}
        </label>
      }
    </fieldset>
  `,
  host: { class: 'block' },
})
export class RadioField extends FieldBase {}
