import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-unknown-field',
  template: `
    <div class="border border-dashed border-border-input rounded-card p-section text-fg-muted">
      <p class="m-0">Nieobsługiwany typ pola: {{ field().type }}</p>
      <p class="m-0 font-semibold">{{ field().title }}</p>
    </div>
  `,
  host: { class: 'block' },
})
export class UnknownField extends FieldBase {}
