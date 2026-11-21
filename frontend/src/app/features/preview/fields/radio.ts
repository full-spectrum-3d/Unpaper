import { Component, computed, inject } from '@angular/core';
import { FormState } from '../form-state';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-radio-field',
  template: `
    <fieldset class="m-0 p-0 border-0" [attr.aria-describedby]="groupDescribedBy()">
      <legend [class]="labelClass()">{{ label() }}</legend>
      @if (hasDescription()) {
        <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
      }
      @for (o of field().options ?? []; track o.id) {
        <label class="flex items-center gap-2 py-1">
          <input
            type="radio"
            class="focus-ring"
            [name]="field().id"
            [value]="o.name"
            [checked]="value() === o.name"
            [attr.aria-invalid]="error() ? 'true' : null"
            (change)="set(o.name)"
          />
          {{ o.name }}
        </label>
      }
      @if (error(); as text) {
        <small [id]="errorId()" class="block text-danger"
          ><span aria-hidden="true">✕</span> {{ text }}</small
        >
      }
    </fieldset>
  `,
  host: { class: 'block' },
})
export class RadioField extends FieldBase {
  // shortcut: local error wiring, replaced by FieldBase.error in Task 5.
  private readonly formState = inject(FormState);
  protected readonly error = computed(() => this.formState.error(this.field()));
  protected readonly errorId = computed(() => this.id() + '-error');
  protected readonly groupDescribedBy = computed(
    () => [this.describedBy(), this.error() && this.errorId()].filter(Boolean).join(' ') || null,
  );
}
