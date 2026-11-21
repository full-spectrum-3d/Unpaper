import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-select-field',
  template: `
    <label [for]="id()" [class]="labelClass()">{{ label() }}</label>
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <select
      class="block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y focus-ring"
      [id]="id()"
      [attr.aria-describedby]="describedBy()"
      (change)="set($any($event.target).value)"
    >
      <option value="" [selected]="!value()">Wybierz</option>
      @for (o of field().options ?? []; track o.id) {
        <option [value]="o.name" [selected]="value() === o.name">{{ o.name }}</option>
      }
      @if (!field().options?.length && field().dictionaryName) {
        <option disabled>Słownik: {{ field().dictionaryName }}</option>
      }
    </select>
  `,
  host: { class: 'block' },
})
export class SelectField extends FieldBase {}
