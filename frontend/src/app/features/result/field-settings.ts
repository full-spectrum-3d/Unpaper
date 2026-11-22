import { Component, computed, inject, input, linkedSignal, output, signal } from '@angular/core';
import { TextField } from '../../shared/ui/text-field/text-field';
import { FormField } from '../preview/form-definition';
import {
  DefaultValue,
  EXTERNAL_SYSTEM,
  FieldPatch,
  htmlToText,
  stateTypesFor,
  takesDescription,
  takesInitialData,
  takesReadOnly,
  takesStates,
  takesTextDefault,
  techNameError,
} from './form-edit';
import { InitialDataCatalog } from './initial-data';
import { StatesEditor } from './states-editor';

type DefaultMode = DefaultValue['kind'];

const SELECT_CLASS =
  'block w-full max-w-md text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring';

/**
 * Less common settings of the component spec ("Specyfikacja poszczególnych komponentów"), folded under
 * "Więcej ustawień": techName, description, read-only, default value
 * (fixed or from initial data) and dynamic states.
 */
@Component({
  selector: 'app-field-settings',
  imports: [TextField, StatesEditor],
  template: `
    @let f = field();
    <details
      class="group rounded-field border border-border"
      [open]="open()"
      (toggle)="onToggle($event)"
    >
      <summary
        class="cursor-pointer select-none px-2 py-1.5 font-semibold text-primary focus-ring rounded-field"
      >
        Więcej ustawień<span class="sr-only"> {{ f.title || f.techName }}</span>
      </summary>
      <div class="flex flex-col gap-3 p-2 pt-1">
        <app-text-field
          class="max-w-md"
          label="Nazwa techniczna"
          description="Identyfikator pola w JSON-ie i w warunkach JSONata; zmiana poprawia też warunki."
          [required]="true"
          [value]="f.techName"
          [error]="techNameErr() ?? undefined"
          (change)="commitTechName($event)"
        />

        @if (description()) {
          <div>
            <label [for]="id + '-description'" class="block text-label font-label mb-1.5"
              >Opis</label
            >
            <textarea
              [id]="id + '-description'"
              rows="2"
              class="block w-full text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
              [value]="descriptionText()"
              (change)="commitDescription($event)"
            ></textarea>
          </div>
        }

        @if (readOnly()) {
          <div class="flex flex-col gap-1.5">
            <label class="flex items-center gap-2">
              <input
                type="checkbox"
                class="focus-ring"
                [checked]="!!f.readOnly"
                [disabled]="readOnlyLocked()"
                [attr.aria-describedby]="readOnlyLocked() ? id + '-ro-hint' : null"
                (change)="patch.emit({ readOnly: $any($event.target).checked })"
              />
              Pole tylko do odczytu
            </label>
            @if (readOnlyLocked()) {
              <small [id]="id + '-ro-hint'" class="block text-fg-muted"
                >Te dane inicjalne nie mogą być zmieniane przez użytkownika.</small
              >
            }
          </div>
        }

        @if (defaultModes().length > 1) {
          <div class="flex flex-wrap items-start gap-3">
            <div>
              <label [for]="id + '-default'" class="block text-label font-label mb-1.5"
                >Wartość domyślna</label
              >
              <select [id]="id + '-default'" [class]="selectClass" (change)="changeMode($event)">
                @for (m of defaultModes(); track m) {
                  <option [value]="m" [selected]="m === mode()">{{ modeLabels[m] }}</option>
                }
              </select>
            </div>
            @if (mode() === 'value') {
              @if (f.type === 'SELECT' && !f.dictionaryName) {
                <div class="grow basis-48">
                  <label [for]="id + '-default-value'" class="block text-label font-label mb-1.5"
                    >Domyślna opcja</label
                  >
                  <select
                    [id]="id + '-default-value'"
                    [class]="selectClass"
                    (change)="commitValue($any($event.target).value)"
                  >
                    <option value="" [selected]="!fixedValue()">— wybierz —</option>
                    @for (o of f.options ?? []; track o.id) {
                      <option [value]="o.name" [selected]="o.name === fixedValue()">
                        {{ o.name }}
                      </option>
                    }
                  </select>
                </div>
              } @else {
                <app-text-field
                  class="grow basis-48"
                  [label]="f.type === 'SELECT' ? 'Domyślna pozycja słownika' : 'Wartość'"
                  [value]="fixedValue()"
                  (change)="commitValue($any($event.target).value)"
                />
              }
            }
            @if (mode() === 'initial') {
              <div class="grow basis-64">
                <label [for]="id + '-initial'" class="block text-label font-label mb-1.5"
                  >Dane inicjalne</label
                >
                <select
                  [id]="id + '-initial'"
                  [class]="selectClass"
                  (change)="commitInitial($any($event.target).value)"
                >
                  <option value="" [selected]="!initialRef()">— wybierz atrybut —</option>
                  @for (g of initialGroups(); track g.name) {
                    <optgroup [label]="g.name">
                      @for (a of g.attributes; track a.ref) {
                        <option [value]="a.ref" [selected]="a.ref === initialRef()">
                          {{ a.label }}{{ a.editable ? '' : ' (tylko do odczytu)' }}
                        </option>
                      }
                    </optgroup>
                  }
                </select>
              </div>
            }
          </div>
        }

        @if (states()) {
          <app-states-editor
            [value]="f.states ?? []"
            [types]="stateTypes()"
            (changed)="patch.emit({ states: $event })"
          />
        }
      </div>
    </details>
  `,
  host: { class: 'block' },
})
export class FieldSettings {
  readonly field = input.required<FormField>();
  /** techNames used in the whole form, the field's own included. */
  readonly taken = input<ReadonlySet<string>>(new Set());
  readonly patch = output<FieldPatch>();
  readonly rename = output<string>();

  private static nextId = 0;
  protected readonly id = `field-settings-${FieldSettings.nextId++}`;
  protected readonly selectClass = SELECT_CLASS;
  protected readonly modeLabels: Record<DefaultMode, string> = {
    none: 'Brak',
    value: 'Stała wartość',
    initial: 'Dane inicjalne',
  };
  private readonly catalog = inject(InitialDataCatalog).sources;
  /** Kept open across re-renders after an edit. */
  protected readonly open = signal(false);

  protected readonly description = computed(() => takesDescription(this.field().type));
  protected readonly descriptionText = computed(() => htmlToText(this.field().description));
  protected readonly readOnly = computed(() => takesReadOnly(this.field().type));
  protected readonly states = computed(() => takesStates(this.field()));
  protected readonly stateTypes = computed(() => stateTypesFor(this.field()));
  protected readonly techNameErr = signal<string | null>(null);

  protected readonly initialRef = computed(() => {
    const f = this.field();
    return f.defaultValueType === EXTERNAL_SYSTEM && typeof f.defaultValue === 'string'
      ? f.defaultValue
      : '';
  });
  /** Attributes for this field type, grouped by source; the field's own ref stays even if unknown. */
  protected readonly initialGroups = computed(() => {
    const type = this.field().type;
    const groups = this.catalog()
      .map((s) => ({ name: s.name, attributes: s.attributes.filter((a) => a.fieldType === type) }))
      .filter((g) => g.attributes.length);
    const ref = this.initialRef();
    if (ref && !groups.some((g) => g.attributes.some((a) => a.ref === ref)))
      groups.push({
        name: 'Obecna wartość',
        attributes: [{ ref, label: ref, editable: true, attribute: ref, fieldType: type }],
      });
    return groups;
  });
  private readonly attribute = computed(() =>
    this.catalog()
      .flatMap((s) => s.attributes)
      .find((a) => a.ref === this.initialRef()),
  );
  protected readonly readOnlyLocked = computed(() => this.attribute()?.editable === false);

  protected readonly defaultModes = computed<DefaultMode[]>(() => {
    const type = this.field().type;
    return [
      'none',
      ...(takesTextDefault(type) || type === 'SELECT' ? (['value'] as const) : []),
      ...(takesInitialData(type) ? (['initial'] as const) : []),
    ];
  });
  /** Local choice until a value or an attribute is picked; follows the field after each save. */
  protected readonly mode = linkedSignal<DefaultMode>(() => {
    const f = this.field();
    if (f.defaultValueType === EXTERNAL_SYSTEM) return 'initial';
    const dv = f.defaultValue;
    return dv ? 'value' : 'none';
  });
  protected readonly fixedValue = computed(() => {
    const f = this.field();
    if (f.defaultValueType === EXTERNAL_SYSTEM) return '';
    const dv = f.defaultValue;
    return dv ?? '';
  });

  protected onToggle(event: Event): void {
    this.open.set((event.target as HTMLDetailsElement).open);
  }

  protected commitTechName(event: Event): void {
    const name = (event.target as HTMLInputElement).value.trim();
    if (name === this.field().techName) return this.techNameErr.set(null);
    const taken = new Set(this.taken());
    taken.delete(this.field().techName);
    const error = techNameError(name, taken);
    this.techNameErr.set(error);
    if (!error) this.rename.emit(name);
  }

  protected commitDescription(event: Event): void {
    const text = (event.target as HTMLTextAreaElement).value.trim();
    if (text !== this.descriptionText()) this.patch.emit({ description: text });
  }

  protected changeMode(event: Event): void {
    const mode = (event.target as HTMLSelectElement).value as DefaultMode;
    this.mode.set(mode);
    if (mode === 'none') this.patch.emit({ defaultValue: { kind: 'none' } });
  }

  protected commitValue(raw: string): void {
    const value = raw.trim();
    if (!value) return this.patch.emit({ defaultValue: { kind: 'none' } });
    // `defaultValue` is a string in the import format; for a list it is the option name.
    this.patch.emit({ defaultValue: { kind: 'value', value } });
  }

  protected commitInitial(ref: string): void {
    if (!ref) return this.patch.emit({ defaultValue: { kind: 'none' } });
    const attr = this.catalog()
      .flatMap((s) => s.attributes)
      .find((a) => a.ref === ref);
    this.patch.emit({ defaultValue: { kind: 'initial', ref, editable: attr?.editable ?? true } });
  }
}
