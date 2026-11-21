import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-date-field',
  template: `
    <label [for]="id()" class="block text-label font-semibold">{{ field().title }}</label>
    @if (hasText(field().description)) {
      <div class="text-fg-muted" [innerHTML]="field().description"></div>
    }
    <input
      type="date"
      class="block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y focus-ring"
      [id]="id()"
      [value]="value()"
      (input)="set($any($event.target).value)"
    />
  `,
  host: { class: 'block' },
})
export class DateField extends FieldBase {
  protected readonly id = computed(() => 'fld-' + this.field().id);
}
