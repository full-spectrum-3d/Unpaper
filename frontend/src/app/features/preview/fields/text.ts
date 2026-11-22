import { Component, computed } from '@angular/core';
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
      [required]="required()"
      [autocomplete]="autocomplete()"
      [inputmode]="field().type === 'NUMBER' ? 'decimal' : undefined"
      [error]="error() ?? undefined"
      [tooltip]="tooltip()"
      [tag]="tag()"
      [value]="value()"
      (valueChange)="set($event)"
    />
  `,
})
export class TextFieldType extends FieldBase {
  protected readonly autocomplete = computed(() => autocompleteFor(this.field().techName));
}

/** The applicant's own data only: another person's or a company's fields (…_inna_osoba, …_siedziba) get none. */
const AUTOCOMPLETE: Record<string, string> = {
  imie: 'given-name',
  nazwisko: 'family-name',
  kod_pocztowy: 'postal-code',
  miejscowosc: 'address-level2',
  ulica: 'address-line1',
  email: 'email',
  e_mail: 'email',
  adres_email: 'email',
  adres_e_mail: 'email',
  telefon: 'tel',
  numer_telefonu: 'tel',
};

/** WCAG 1.3.5 token for a known personal-data techName; the applicant's foreign address counts too. */
export function autocompleteFor(techName: string | undefined): string | undefined {
  return AUTOCOMPLETE[(techName ?? '').replace(/_zagranica$/, '')];
}
