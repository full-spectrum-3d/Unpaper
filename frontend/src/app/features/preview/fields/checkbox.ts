import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-checkbox-field',
  template: `
    @if (field().options?.length) {
      <fieldset class="m-0 p-0 border-0" [attr.aria-describedby]="describedBy()">
        <legend [class]="labelClass()">{{ label() }}</legend>
        @if (hasDescription()) {
          <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
        }
        @for (o of field().options!; track o.id) {
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
    } @else {
      <label class="flex items-center gap-2 py-1">
        <input
          type="checkbox"
          class="focus-ring"
          [attr.aria-describedby]="describedBy()"
          [checked]="value().includes(label())"
          (change)="toggle(label(), $any($event.target).checked)"
        />
        {{ label() }}
      </label>
      @if (hasDescription()) {
        <div class="text-fg-muted" [id]="descId()" [innerHTML]="field().description"></div>
      }
    }
  `,
  host: { class: 'block' },
})
export class CheckboxField extends FieldBase<string[]> {
  protected toggle(name: string, on: boolean) {
    this.set(on ? [...this.value(), name] : this.value().filter((n) => n !== name));
  }
}
