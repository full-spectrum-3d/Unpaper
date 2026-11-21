import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-checkbox-field',
  template: `
    <fieldset class="m-0 p-0 border-0" [attr.aria-describedby]="describedBy()">
      <legend class="block text-label font-semibold">{{ label() }}</legend>
      @if (hasText(field().description)) {
      <div class="text-fg-muted" [id]="descId()" [innerHTML]="field().description"></div>
    }
      @for (o of field().options?.length ? field().options! : [{ id: field().id, name: label() }]; track o.id) {
        <label class="flex items-center gap-2 py-1">
          <input
            type="checkbox"
            class="focus-ring"
            [checked]="value().includes(o.name)"
            (change)="toggle(o.name, $any($event.target).checked)"
          />
          {{ o.name }}
        </label>
      }
    </fieldset>
  `,
  host: { class: 'block' },
})
export class CheckboxField extends FieldBase<string[]> {
  protected toggle(name: string, on: boolean) {
    this.set(on ? [...this.value(), name] : this.value().filter((n) => n !== name));
  }
}
