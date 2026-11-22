import {
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { Button } from '../../shared/ui/button/button';
import { TextField } from '../../shared/ui/text-field/text-field';
import {
  EDITABLE_TYPES,
  EditableType,
  NewField,
  isChoice,
  optionsError,
  parseOptions,
} from './form-edit';

/** "Dodaj pole" button that opens an inline form for a new field at the end of a section. */
@Component({
  selector: 'app-add-field',
  imports: [Button, TextField],
  template: `
    @if (open()) {
      <form
        class="border border-dashed border-border-input rounded-card p-section flex flex-col gap-3"
        novalidate
        (submit)="submit($event)"
      >
        <fieldset class="flex flex-col gap-3">
          <legend class="font-semibold mb-1">Nowe pole w sekcji „{{ sectionTitle() }}”</legend>
          <div class="flex flex-wrap items-start gap-3">
            <app-text-field
              class="grow basis-64"
              label="Etykieta"
              [required]="true"
              [(value)]="title"
              [error]="titleError() ?? undefined"
            />
            <div class="basis-48">
              <label [for]="id + '-type'" class="block text-label font-label mb-1.5"
                >Typ pola</label
              >
              <select
                [id]="id + '-type'"
                class="block w-full text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                (change)="type.set($any($event.target).value)"
              >
                @for (t of types; track t.value) {
                  <option [value]="t.value" [selected]="t.value === type()">{{ t.label }}</option>
                }
              </select>
            </div>
            <label class="flex items-center gap-2 mt-7">
              <input
                type="checkbox"
                class="focus-ring"
                [checked]="required()"
                (change)="required.set($any($event.target).checked)"
              />
              Wymagane
            </label>
          </div>
          @if (choice()) {
            <div>
              <label [for]="id + '-options'" class="block text-label font-label">Opcje</label>
              <small [id]="id + '-options-hint'" class="block text-fg-muted mb-1.5"
                >Jedna opcja w wierszu.</small
              >
              <textarea
                [id]="id + '-options'"
                rows="3"
                class="block w-full text-fg text-body border rounded-field px-field-x py-field-y bg-surface focus-ring"
                [class]="optionsErr() ? 'border-danger' : 'border-border-input'"
                [value]="options()"
                [attr.aria-invalid]="optionsErr() ? 'true' : null"
                [attr.aria-describedby]="
                  id + '-options-hint' + (optionsErr() ? ' ' + id + '-options-error' : '')
                "
                (input)="options.set($any($event.target).value)"
              ></textarea>
              @if (optionsErr(); as text) {
                <small [id]="id + '-options-error'" class="block text-danger"
                  ><span aria-hidden="true">✕</span> {{ text }}</small
                >
              }
            </div>
          }
        </fieldset>
        <div class="flex gap-2">
          <button appButton type="submit" variant="primary">Dodaj</button>
          <button appButton type="button" (click)="close()">Anuluj</button>
        </div>
      </form>
    } @else {
      <button appButton type="button" class="add" (click)="openForm()">
        Dodaj pole<span class="sr-only"> w sekcji {{ sectionTitle() }}</span>
      </button>
    }
  `,
  host: { class: 'block' },
})
export class AddField {
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly sectionTitle = input.required<string>();
  readonly add = output<NewField>();

  private static nextId = 0;
  protected readonly id = `add-field-${AddField.nextId++}`;
  protected readonly types = Object.entries(EDITABLE_TYPES).map(([value, label]) => ({
    value: value as EditableType,
    label,
  }));

  protected readonly open = signal(false);
  protected readonly title = signal('');
  protected readonly type = signal<EditableType>('TEXT_FIELD');
  protected readonly required = signal(false);
  protected readonly options = signal('');
  protected readonly titleError = signal<string | null>(null);
  protected readonly optionsErr = signal<string | null>(null);
  protected readonly choice = computed(() => isChoice(this.type()));

  protected openForm(): void {
    this.open.set(true);
    this.focusLater('input');
  }

  protected close(): void {
    this.reset();
    this.focusLater('button.add');
  }

  protected submit(event: Event): void {
    event.preventDefault();
    const title = this.title().trim();
    const options = this.choice() ? parseOptions(this.options()) : [];
    this.titleError.set(title ? null : 'Podaj etykietę pola.');
    this.optionsErr.set(optionsError(this.type(), options));
    if (this.titleError()) return this.focusLater('input');
    if (this.optionsErr()) return this.focusLater('textarea');
    this.add.emit({ type: this.type(), title, required: this.required(), options });
    // The parent moves focus to the new field.
    this.reset();
  }

  private reset(): void {
    this.open.set(false);
    this.title.set('');
    this.type.set('TEXT_FIELD');
    this.required.set(false);
    this.options.set('');
    this.titleError.set(null);
    this.optionsErr.set(null);
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
