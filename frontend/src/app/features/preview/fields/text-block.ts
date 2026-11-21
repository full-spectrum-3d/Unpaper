import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-text-block-field',
  template: `<div [innerHTML]="hasText(field().description) ? field().description : field().title"></div>`,
  host: { class: 'block' },
})
export class TextBlockField extends FieldBase {}
