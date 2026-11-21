import { Component } from '@angular/core';
import { TextField } from '../../../shared/ui/text-field/text-field';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-text-field-type',
  imports: [TextField],
  template: `
    <app-text-field
      [label]="label()"
      [description]="descriptionText()"
      [labelHidden]="!hasTitle()"
      [readonly]="readOnly()"
      [inputmode]="field().type === 'NUMBER' ? 'decimal' : undefined"
      [error]="error() ?? undefined"
      [tooltip]="tooltip()"
      [tag]="tag()"
      [value]="value()"
      (valueChange)="set($event)"
    />
  `,
})
export class TextFieldType extends FieldBase {}
