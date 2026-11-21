import { Component } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-date-field',
  imports: [FieldLabel],
  template: `
    <app-field-label
      [label]="label()"
      [for]="id()"
      [hidden]="!hasTitle()"
      [tooltip]="tooltip()"
      [tag]="tag()"
    />
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <input
      type="date"
      [class]="controlClass()"
      [id]="id()"
      [readOnly]="readOnly()"
      [attr.aria-describedby]="describedBy()"
      [attr.aria-invalid]="error() ? 'true' : null"
      [value]="value()"
      (input)="set($any($event.target).value)"
    />
    @if (error(); as text) {
      <small [id]="errorId()" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
  `,
  host: { class: 'block' },
})
export class DateField extends FieldBase {}
