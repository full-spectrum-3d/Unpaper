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
import { ConsentsEditor } from './consents-editor';
import {
  ConsentInput,
  EDITABLE_TYPES,
  EditableType,
  FORMAT_VALIDATORS,
  FormatValidator,
  NewField,
  isChoice,
  isConsent,
  isContent,
  optionsError,
  parseOptions,
  takesValue,
  titleOptional,
} from './form-edit';
import { PROPOSED_PREFIX, SelectDictionaries } from './select-dictionaries';

const FIRST_CONSENT: ConsentInput = { text: '' };

/** "Dodaj pole" button that opens an inline form for a new field at the end of a section. */
@Component({
  selector: 'app-add-field',
  imports: [Button, TextField, ConsentsEditor],
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
              [label]="optionalTitle() ? 'Tytuł (opcjonalnie)' : 'Etykieta'"
              [required]="!optionalTitle()"
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
                (change)="changeType($any($event.target).value)"
              >
                @for (t of typeChoices(); track t.value) {
                  <option [value]="t.value" [selected]="t.value === type()">{{ t.label }}</option>
                }
              </select>
            </div>
            @if (type() === 'TEXT_FIELD') {
              <div class="basis-48">
                <label [for]="id + '-format'" class="block text-label font-label mb-1.5"
                  >Walidator</label
                >
                <select
                  [id]="id + '-format'"
                  class="block w-full text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                  (change)="format.set($any($event.target).value || null)"
                >
                  <option value="" [selected]="!format()">Brak</option>
                  @for (v of formats; track v.value) {
                    <option [value]="v.value" [selected]="v.value === format()">
                      {{ v.label }}
                    </option>
                  }
                </select>
              </div>
            }
            @if (inputType()) {
              <label class="flex items-center gap-2 mt-7">
                <input
                  type="checkbox"
                  class="focus-ring"
                  [checked]="required()"
                  (change)="required.set($any($event.target).checked)"
                />
                Wymagane
              </label>
            }
          </div>
          @if (type() === 'SELECT') {
            <div>
              <label [for]="id + '-source'" class="block text-label font-label mb-1.5"
                >Źródło opcji</label
              >
              <select
                [id]="id + '-source'"
                class="block w-full max-w-md text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                (change)="changeSource($event)"
              >
                <option value="" [selected]="!dictionary()">Własne opcje</option>
                @for (d of dictionaries(); track d.name) {
                  <option [value]="d.name" [selected]="d.name === dictionary()">
                    Słownik: {{ d.name }}
                  </option>
                }
                @if (proposed().length) {
                  <optgroup label="Proponowane słowniki (wstawia pozycje jako opcje)">
                    @for (d of proposed(); track d.name) {
                      <option [value]="PROPOSED + d.name">{{ d.title }}</option>
                    }
                  </optgroup>
                }
              </select>
            </div>
          }
          @if (needsOptions()) {
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
          @if (content()) {
            <div>
              <label [for]="id + '-content'" class="block text-label font-label"
                >Treść<span class="text-danger" aria-hidden="true"> *</span></label
              >
              <small [id]="id + '-content-hint'" class="block text-fg-muted mb-1.5"
                >Akapity oddziel pustą linią.</small
              >
              <textarea
                [id]="id + '-content'"
                rows="4"
                aria-required="true"
                class="block w-full text-fg text-body border rounded-field px-field-x py-field-y bg-surface focus-ring"
                [class]="contentErr() ? 'border-danger' : 'border-border-input'"
                [value]="contentText()"
                [attr.aria-invalid]="contentErr() ? 'true' : null"
                [attr.aria-describedby]="
                  id + '-content-hint' + (contentErr() ? ' ' + id + '-content-error' : '')
                "
                (input)="contentText.set($any($event.target).value)"
              ></textarea>
              @if (contentErr(); as text) {
                <small [id]="id + '-content-error'" class="block text-danger"
                  ><span aria-hidden="true">✕</span> {{ text }}</small
                >
              }
            </div>
          }
          @if (consent()) {
            <app-consents-editor
              [value]="consentsStart()"
              [showErrors]="submitted()"
              (changed)="consents.set($event)"
            />
            <label class="flex items-center gap-2">
              <input
                type="checkbox"
                class="focus-ring"
                [checked]="consentsRequired()"
                (change)="consentsRequired.set($any($event.target).checked)"
              />
              Zgody wymagane
            </label>
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
  /** Types offered (e.g. only INFO_SECTION on the finish page); null = all. */
  readonly types = input<readonly EditableType[] | null>(null);
  readonly add = output<NewField>();

  private static nextId = 0;
  protected readonly id = `add-field-${AddField.nextId++}`;
  protected readonly typeChoices = computed(() => {
    const allowed = this.types();
    return Object.entries(EDITABLE_TYPES)
      .map(([value, label]) => ({ value: value as EditableType, label }))
      .filter((t) => !allowed || allowed.includes(t.value));
  });
  private readonly catalog = inject(SelectDictionaries);
  protected readonly dictionaries = this.catalog.list;
  protected readonly proposed = this.catalog.proposed;
  protected readonly PROPOSED = PROPOSED_PREFIX;

  protected readonly open = signal(false);
  protected readonly title = signal('');
  protected readonly type = signal<EditableType>('TEXT_FIELD');
  protected readonly required = signal(false);
  protected readonly format = signal<FormatValidator | null>(null);
  protected readonly formats = Object.entries(FORMAT_VALIDATORS).map(([value, label]) => ({
    value: value as FormatValidator,
    label,
  }));
  protected readonly options = signal('');
  /** Name of the chosen predefined dictionary; '' = own options. */
  protected readonly dictionary = signal('');
  protected readonly contentText = signal('');
  /** Initial list for the consents editor; edits arrive in `consents`. */
  protected readonly consentsStart = signal<readonly ConsentInput[]>([FIRST_CONSENT]);
  private readonly consents = signal<readonly ConsentInput[]>([FIRST_CONSENT]);
  protected readonly consentsRequired = signal(true);
  protected readonly submitted = signal(false);
  protected readonly titleError = signal<string | null>(null);
  protected readonly optionsErr = signal<string | null>(null);
  protected readonly contentErr = signal<string | null>(null);
  protected readonly inputType = computed(() => takesValue(this.type()));
  protected readonly optionalTitle = computed(() => titleOptional(this.type()));
  protected readonly content = computed(() => isContent(this.type()));
  protected readonly consent = computed(() => isConsent(this.type()));
  protected readonly needsOptions = computed(
    () => isChoice(this.type()) && !(this.type() === 'SELECT' && this.dictionary()),
  );

  protected openForm(): void {
    this.type.set(this.typeChoices()[0]?.value ?? 'TEXT_FIELD');
    this.open.set(true);
    this.focusLater('input');
  }

  protected close(): void {
    this.reset();
    this.focusLater('button.add');
  }

  /** A proposed dictionary fills the options box (still editable) and leaves the source on own options. */
  protected changeSource(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const value = select.value;
    if (!value.startsWith(PROPOSED_PREFIX)) return this.dictionary.set(value);
    const proposal = this.proposed().find((d) => PROPOSED_PREFIX + d.name === value);
    this.dictionary.set('');
    select.value = '';
    if (proposal) {
      this.options.set(proposal.items.join('\n'));
      this.optionsErr.set(null);
    }
  }

  protected changeType(type: EditableType): void {
    this.type.set(type);
    this.titleError.set(null);
  }

  protected submit(event: Event): void {
    event.preventDefault();
    this.submitted.set(true);
    const type = this.type();
    const title = this.title().trim();
    const options = this.needsOptions() ? parseOptions(this.options()) : [];
    const text = this.contentText().trim();
    const consents = this.consents();
    this.titleError.set(title || this.optionalTitle() ? null : 'Podaj etykietę pola.');
    this.optionsErr.set(this.needsOptions() ? optionsError(type, options) : null);
    this.contentErr.set(this.content() && !text ? 'Podaj treść.' : null);
    const consentsInvalid = this.consent() && !consents.every((c) => c.text.trim());
    if (this.titleError()) return this.focusLater('input');
    if (this.optionsErr()) return this.focusLater(`#${this.id}-options`);
    if (this.contentErr()) return this.focusLater(`#${this.id}-content`);
    if (consentsInvalid) return this.focusLater('app-consents-editor [aria-invalid="true"]');
    const chosen = this.dictionaries().find((d) => d.name === this.dictionary());
    this.add.emit({
      type,
      title,
      required: this.inputType() && this.required(),
      options,
      dictionary: type === 'SELECT' && chosen ? { name: chosen.name } : null,
      content: this.content() ? text : undefined,
      consents: this.consent() ? consents : undefined,
      consentsRequired: this.consent() ? this.consentsRequired() : undefined,
      format: type === 'TEXT_FIELD' ? this.format() : null,
    });
    // The parent moves focus to the new field.
    this.reset();
  }

  private reset(): void {
    this.open.set(false);
    this.title.set('');
    this.type.set('TEXT_FIELD');
    this.required.set(false);
    this.format.set(null);
    this.options.set('');
    this.dictionary.set('');
    this.contentText.set('');
    this.consentsStart.set([FIRST_CONSENT]);
    this.consents.set([FIRST_CONSENT]);
    this.consentsRequired.set(true);
    this.submitted.set(false);
    this.titleError.set(null);
    this.optionsErr.set(null);
    this.contentErr.set(null);
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
