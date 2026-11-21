import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-textarea-field',
  imports: [FieldLabel],
  template: `
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <app-field-label
      [label]="label()"
      [for]="id()"
      [hidden]="!hasTitle()"
      [tooltip]="tooltip()"
      [tag]="tag()"
    />
    <textarea
      class="min-h-32"
      [class]="controlClass()"
      [id]="id()"
      rows="5"
      maxlength="8000"
      [readOnly]="readOnly()"
      [attr.aria-describedby]="describedByAll()"
      [attr.aria-invalid]="error() ? 'true' : null"
      [value]="value()"
      (input)="set($any($event.target).value)"
    ></textarea>
    <small [id]="id() + '-count'" class="block text-right text-fg-muted"
      >{{ value().length }}/8000</small
    >
    @if (error(); as text) {
      <small [id]="errorId()" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
  `,
  host: { class: 'block' },
})
export class TextareaField extends FieldBase {
  protected readonly describedByAll = computed(() =>
    [this.describedBy(), this.id() + '-count'].filter(Boolean).join(' '),
  );
}
