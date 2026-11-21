import { Component } from '@angular/core';
import { TextField } from '../../../shared/ui/text-field/text-field';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-text-field-type',
  imports: [TextField],
  template: `
    <app-text-field
      [label]="field().title"
      [description]="descriptionText()"
      [readonly]="!!field().readOnly"
      [inputmode]="field().type === 'NUMBER' ? 'decimal' : undefined"
      [value]="value()"
      (valueChange)="set($event)"
    />
  `,
})
export class TextFieldType extends FieldBase {
  protected descriptionText() {
    const d = this.field().description;
    return this.hasText(d) ? new DOMParser().parseFromString(d!, 'text/html').body.textContent!.trim() : undefined;
  }
}
