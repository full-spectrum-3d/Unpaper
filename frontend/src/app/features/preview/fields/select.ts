import { Component, computed } from '@angular/core';
import { Combobox } from '../../../shared/ui/combobox/combobox';
import { isSearchable, selectOptions } from '../select-options';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-select-field',
  imports: [Combobox],
  template: `
    <app-combobox
      [label]="label()"
      [labelHidden]="!hasTitle()"
      [options]="options()"
      [searchable]="searchable()"
      [describedBy]="hasDescription() ? descId() : null"
      [error]="error() ?? undefined"
      [readonly]="readOnly()"
      [tooltip]="tooltip()"
      [tag]="tag()"
      [emptyText]="emptyText()"
      [value]="value() ?? ''"
      (valueChange)="set($event)"
    >
      @if (hasDescription()) {
        <div
          description
          class="text-fg-muted mb-1.5"
          [id]="descId()"
          [innerHTML]="field().description"
        ></div>
      }
    </app-combobox>
  `,
  host: { class: 'block' },
})
export class SelectField extends FieldBase {
  protected readonly options = computed(() => selectOptions(this.field()));
  protected readonly searchable = computed(() => isSearchable(this.field(), this.options().length));
  protected readonly emptyText = computed(() =>
    !this.options().length && this.field().dictionaryName
      ? `Brak pozycji w słowniku ${this.field().dictionaryName}`
      : 'Brak wyników',
  );
}
