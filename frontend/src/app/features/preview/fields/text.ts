import { Component, computed, inject } from '@angular/core';
import { TextField } from '../../../shared/ui/text-field/text-field';
import { FormState } from '../form-state';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-text-field-type',
  imports: [TextField],
  template: `
    <app-text-field
      [label]="label()"
      [description]="descriptionText()"
      [labelHidden]="!hasTitle()"
      [readonly]="!!field().readOnly"
      [inputmode]="field().type === 'NUMBER' ? 'decimal' : undefined"
      [error]="error() ?? undefined"
      [value]="value()"
      (valueChange)="set($event)"
    />
  `,
})
export class TextFieldType extends FieldBase {
  // shortcut: local error wiring, replaced by FieldBase.error in Task 5.
  private readonly formState = inject(FormState);
  protected readonly error = computed(() => this.formState.error(this.field()));
}
