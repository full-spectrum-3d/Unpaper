import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-date-field',
  template: `
    <label [for]="id()" class="block text-label font-semibold">{{ label() }}</label>
    @if (hasText(field().description)) {
      <div class="text-fg-muted" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <input
      type="date"
      class="block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y focus-ring"
      [id]="id()"
      [attr.aria-describedby]="describedBy()"
      [value]="value()"
      (input)="set($any($event.target).value)"
    />
  `,
  host: { class: 'block' },
})
export class DateField extends FieldBase {
}
