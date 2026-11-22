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
import { FormField } from '../preview/form-definition';
import {
  EDITABLE_TYPES,
  EditableType,
  FieldPatch,
  isChoice,
  isEditableType,
  isRegistryField,
  isSection,
  optionsError,
  parseOptions,
  typeLabel,
} from './form-edit';

/** Edit controls of one field: label, type, requiredness, options, reordering and removal with confirmation. */
@Component({
  selector: 'app-field-row',
  imports: [Button, TextField],
  template: `
    @let f = field();
    <fieldset class="border border-border rounded-card p-section bg-surface flex flex-col gap-3">
      <legend class="px-1 font-semibold [overflow-wrap:anywhere]">
        {{ f.title || '(bez etykiety)' }}
        <span class="font-normal text-fg-muted">— {{ typeName() }}</span>
      </legend>
      @if (registry()) {
        <p class="text-fg-muted">Dane z rejestru — pola nie można edytować.</p>
      } @else if (titleEditable()) {
        <div class="flex flex-wrap items-start gap-3">
          <app-text-field
            class="grow basis-64"
            label="Etykieta"
            [required]="true"
            [value]="f.title"
            [error]="titleError() ?? undefined"
            (change)="commitTitle($event)"
          />
          @if (editable()) {
            <div class="basis-48">
              <label [for]="id + '-type'" class="block text-label font-label mb-1.5"
                >Typ pola</label
              >
              <select
                [id]="id + '-type'"
                class="block w-full text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                (change)="changeType($event)"
              >
                @for (t of types; track t.value) {
                  <option [value]="t.value" [selected]="t.value === f.type">{{ t.label }}</option>
                }
              </select>
            </div>
            <label class="flex items-center gap-2 mt-7">
              <input
                type="checkbox"
                class="focus-ring"
                [checked]="required()"
                (change)="patch.emit({ required: $any($event.target).checked })"
              />
              Wymagane
            </label>
          }
        </div>
        @if (editable() && choice()) {
          @if (f.dictionaryName) {
            <p class="text-fg-muted">Opcje ze słownika {{ f.dictionaryName }}.</p>
          } @else {
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
                [value]="optionsText()"
                [attr.aria-invalid]="optionsErr() ? 'true' : null"
                [attr.aria-describedby]="
                  id + '-options-hint' + (optionsErr() ? ' ' + id + '-options-error' : '')
                "
                (change)="commitOptions($event)"
              ></textarea>
              @if (optionsErr(); as text) {
                <small [id]="id + '-options-error'" class="block text-danger"
                  ><span aria-hidden="true">✕</span> {{ text }}</small
                >
              }
            </div>
          }
        }
      } @else {
        <p class="text-fg-muted">Element statyczny — można go tylko usunąć.</p>
      }
      <div class="flex flex-wrap items-center gap-2">
        <button
          appButton
          type="button"
          variant="ghost"
          class="move-up"
          [disabled]="first()"
          (click)="move.emit(-1)"
        >
          <span aria-hidden="true">↑</span> W górę<span class="sr-only">
            {{ f.title || typeName() }}</span
          >
        </button>
        <button
          appButton
          type="button"
          variant="ghost"
          class="move-down"
          [disabled]="last()"
          (click)="move.emit(1)"
        >
          <span aria-hidden="true">↓</span> W dół<span class="sr-only">
            {{ f.title || typeName() }}</span
          >
        </button>
        @if (!removable()) {
          <p class="text-fg-muted">Jedynego elementu strony nie można usunąć.</p>
        } @else if (confirming()) {
          <p [id]="id + '-confirm'">
            Usunąć „{{ f.title || typeName() }}”{{ hasChildren() ? ' razem z polami sekcji' : '' }}?
          </p>
          <button
            appButton
            type="button"
            variant="primary"
            [attr.aria-describedby]="id + '-confirm'"
            (click)="remove.emit()"
          >
            Tak, usuń
          </button>
          <button appButton type="button" (click)="cancelRemove()">Anuluj</button>
        } @else {
          <button appButton type="button" class="remove" (click)="askRemove()">
            Usuń<span class="sr-only"> {{ f.title || typeName() }}</span>
          </button>
        }
      </div>
    </fieldset>
  `,
  host: { class: 'block', '[attr.id]': "'edit-field-' + field().id" },
})
export class FieldRow {
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly field = input.required<FormField>();
  readonly removable = input(true);
  /** First / last among its siblings: the matching move button is disabled. */
  readonly first = input(false);
  readonly last = input(false);
  readonly patch = output<FieldPatch>();
  readonly move = output<-1 | 1>();
  readonly remove = output<void>();

  private static nextId = 0;
  protected readonly id = `field-row-${FieldRow.nextId++}`;
  protected readonly types = Object.entries(EDITABLE_TYPES).map(([value, label]) => ({
    value: value as EditableType,
    label,
  }));

  protected readonly typeName = computed(() => typeLabel(this.field().type));
  protected readonly registry = computed(() => isRegistryField(this.field()));
  protected readonly editable = computed(() => isEditableType(this.field().type));
  protected readonly titleEditable = computed(() => this.editable() || isSection(this.field()));
  protected readonly choice = computed(() => isChoice(this.field().type));
  protected readonly required = computed(
    () => this.field().validation?.includes('REQUIRED') ?? false,
  );
  protected readonly hasChildren = computed(() => !!this.field().repeatingSectionGrid?.length);
  protected readonly optionsText = computed(() =>
    (this.field().options ?? []).map((o) => o.name).join('\n'),
  );
  protected readonly titleError = signal<string | null>(null);
  protected readonly optionsErr = signal<string | null>(null);
  protected readonly confirming = signal(false);

  protected commitTitle(event: Event): void {
    const title = (event.target as HTMLInputElement).value.trim();
    this.titleError.set(title ? null : 'Podaj etykietę pola.');
    if (title && title !== this.field().title) this.patch.emit({ title });
  }

  protected changeType(event: Event): void {
    this.optionsErr.set(null);
    this.patch.emit({ type: (event.target as HTMLSelectElement).value as EditableType });
  }

  protected commitOptions(event: Event): void {
    const options = parseOptions((event.target as HTMLTextAreaElement).value);
    const error = optionsError(this.field().type, options);
    this.optionsErr.set(error);
    if (!error) this.patch.emit({ options });
  }

  protected askRemove(): void {
    this.confirming.set(true);
    this.focusLater(`[aria-describedby="${this.id}-confirm"]`);
  }

  protected cancelRemove(): void {
    this.confirming.set(false);
    this.focusLater('button.remove');
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
