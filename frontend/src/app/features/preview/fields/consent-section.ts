import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-consent-section-field',
  template: `
    <fieldset class="m-0 p-0 border-0" [attr.aria-describedby]="describedBy()">
      <legend [class]="labelClass()">{{ label() }}</legend>
      @if (hasDescription()) {
        <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
      }
      @for (c of field().consentSectionConfig?.consents ?? []; track $index) {
        <label class="flex items-start gap-2 py-1">
          <input
            type="checkbox"
            class="mt-1 focus-ring"
            [checked]="!!value()[$index]"
            (change)="toggle($index, $any($event.target).checked)"
          />
          <span>
            <span [innerHTML]="c.description"></span>
            @if (c.required) {
              <span class="text-danger"> * (wymagana)</span>
            }
          </span>
        </label>
      }
    </fieldset>
  `,
  host: { class: 'block' },
})
export class ConsentSectionField extends FieldBase<boolean[]> {
  protected toggle(i: number, on: boolean) {
    this.set(this.value().map((v, j) => (j === i ? on : v)));
  }
}
