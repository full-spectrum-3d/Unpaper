import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-textarea-field',
  template: `
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <label [for]="id()" [class]="labelClass()">{{ label() }}</label>
    <textarea
      class="block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y focus-ring min-h-32"
      [id]="id()"
      rows="5"
      maxlength="8000"
      [attr.aria-describedby]="describedByAll()"
      [value]="value()"
      (input)="set($any($event.target).value)"
    ></textarea>
    <small [id]="id() + '-count'" class="block text-right text-fg-muted"
      >{{ value().length }}/8000</small
    >
  `,
  host: { class: 'block' },
})
export class TextareaField extends FieldBase {
  protected readonly describedByAll = computed(() =>
    [this.describedBy(), this.id() + '-count'].filter(Boolean).join(' '),
  );
}
