import { Component, computed, forwardRef, input } from '@angular/core';
import { FormField } from './form-definition';
import { isCascade } from './select-options';
import { CheckboxField } from './fields/checkbox';
import { ConsentSectionField } from './fields/consent-section';
import { DictionaryCascadeField } from './fields/dictionary-cascade';
import { DateField } from './fields/date';
import { FileUploaderField } from './fields/file-uploader';
import { RadioField } from './fields/radio';
import { SectionField } from './fields/section';
import { SelectField } from './fields/select';
import { TextBlockField } from './fields/text-block';
import { TextFieldType } from './fields/text';
import { TextareaField } from './fields/textarea';
import { UnknownField } from './fields/unknown';

@Component({
  selector: 'app-field-host',
  imports: [
    forwardRef(() => SectionField),
    TextFieldType,
    TextareaField,
    RadioField,
    SelectField,
    DictionaryCascadeField,
    CheckboxField,
    DateField,
    FileUploaderField,
    TextBlockField,
    ConsentSectionField,
    UnknownField,
  ],
  template: `
    @switch (field().type) {
      @case ('SECTION') {
        <app-section-field [field]="field()" [hidden]="hidden()" />
      }
      @case ('REPEATING_SECTION') {
        <app-section-field [field]="field()" [hidden]="hidden()" />
      }
      @case ('INFO_SECTION') {
        <!-- Backend turns the finish page's text blocks into INFO_SECTION: render as text. -->
        <app-text-block-field [field]="field()" />
      }
      @case ('TEXT_FIELD') {
        <app-text-field-type [field]="field()" />
      }
      @case ('NUMBER') {
        <app-text-field-type [field]="field()" />
      }
      @case ('TEXTAREA') {
        <app-textarea-field [field]="field()" />
      }
      @case ('RADIO') {
        <app-radio-field [field]="field()" />
      }
      @case ('SELECT') {
        @if (cascade()) {
          <app-dictionary-cascade-field [field]="field()" />
        } @else {
          <app-select-field [field]="field()" />
        }
      }
      @case ('CHECKBOX') {
        <app-checkbox-field [field]="field()" />
      }
      @case ('DATEPICKER') {
        <app-date-field [field]="field()" />
      }
      @case ('FILE_UPLOADER') {
        <app-file-uploader-field [field]="field()" />
      }
      @case ('TEXT_BLOCK') {
        <app-text-block-field [field]="field()" />
      }
      @case ('CONSENT_SECTION') {
        <app-consent-section-field [field]="field()" />
      }
      @default {
        <app-unknown-field [field]="field()" />
      }
    }
  `,
  host: { class: 'block', '[attr.data-field-id]': 'field().id' },
})
export class FieldHost {
  readonly field = input.required<FormField>();
  readonly hidden = input<ReadonlySet<string>>(new Set());
  protected readonly cascade = computed(() => isCascade(this.field()));
}
