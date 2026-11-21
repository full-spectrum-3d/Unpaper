import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-textarea-field',
  template: `
    <label [for]="id()" class="block text-label font-semibold">{{ field().title }}</label>
    @if (hasText(field().description)) {
      <div class="text-fg-muted" [innerHTML]="field().description"></div>
    }
    <textarea
      class="block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y focus-ring min-h-32"
      [id]="id()"
      rows="5"
      maxlength="8000"
      [attr.aria-describedby]="id() + '-count'"
      [value]="value()"
      (input)="set($any($event.target).value)"
    ></textarea>
    <small [id]="id() + '-count'" class="block text-right text-fg-muted">{{ value().length }}/8000</small>
  `,
  host: { class: 'block' },
})
export class TextareaField extends FieldBase {
  protected readonly id = computed(() => 'fld-' + this.field().id);
}
