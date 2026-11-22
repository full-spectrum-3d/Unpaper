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
import { ConsentsEditor } from './consents-editor';
import { FieldSettings } from './field-settings';
import {
  ConsentInput,
  EDITABLE_TYPES,
  EXTERNAL_SYSTEM,
  EditableType,
  FORMAT_VALIDATORS,
  FieldPatch,
  FormatValidator,
  formatOf,
  htmlToText,
  isChoice,
  isConsent,
  isContent,
  isEditableType,
  isSection,
  optionsError,
  parseOptions,
  takesFormat,
  takesValue,
  titleOptional,
  typeLabel,
} from './form-edit';
import { PROPOSED_PREFIX, SelectDictionaries, SelectDictionary } from './select-dictionaries';

/**
 * Edit card of one field: drag handle (also moved with arrow keys), label, type, requiredness, options and
 * removal with confirmation. Dragging itself is handled by the editor list around it.
 */
@Component({
  selector: 'app-field-row',
  imports: [Button, TextField, ConsentsEditor, FieldSettings],
  template: `
    @let f = field();
    <div
      class="flex rounded-card border border-border bg-surface shadow-sm"
      [class.opacity-50]="dragging()"
    >
      <div
        class="drag-handle shrink-0 w-7 rounded-l-card flex items-center justify-center text-lg leading-none select-none focus-ring"
        [class]="handleClass()"
        [attr.draggable]="movable() ? 'true' : null"
        [attr.tabindex]="movable() ? 0 : null"
        [attr.role]="movable() ? 'button' : null"
        [attr.aria-roledescription]="movable() ? 'uchwyt przeciągania' : null"
        [attr.aria-label]="movable() ? 'Zmień kolejność: ' + (f.title || typeName()) : null"
        [attr.aria-describedby]="movable() ? 'form-editor-drag-hint' : null"
        [attr.aria-keyshortcuts]="movable() ? 'ArrowUp ArrowDown' : null"
        [attr.aria-hidden]="movable() ? null : 'true'"
        [attr.title]="movable() ? 'Przeciągnij, aby zmienić kolejność (lub strzałki ↑/↓)' : null"
        (keydown)="onHandleKey($event)"
      >
        <span aria-hidden="true">⠿</span>
      </div>
      <fieldset
        class="grow min-w-0 flex flex-col gap-3"
        [class]="folded() ? 'px-section py-2' : 'p-section'"
      >
        <legend
          class="float-left w-full flex flex-wrap items-center gap-2 font-semibold [overflow-wrap:anywhere]"
        >
          @if (section()) {
            <span
              class="text-[11px] uppercase tracking-wide rounded-field px-1.5 py-0.5 bg-topbar text-on-topbar"
              >{{ typeName() }}<span class="sr-only">:</span></span
            >
            <span>{{ f.title || '(bez etykiety)' }}</span>
          } @else {
            <span>{{ f.title || '(bez etykiety)' }}</span>
            <span class="text-[11px] rounded-field px-1.5 py-0.5 bg-primary-subtle text-primary"
              ><span class="sr-only">— </span>{{ typeName() }}</span
            >
            @if (required()) {
              <span class="text-[11px] rounded-field px-1.5 py-0.5 bg-danger-subtle text-danger"
                ><span class="sr-only">, </span>wymagane</span
              >
            }
            @if (format(); as v) {
              <span class="text-[11px] rounded-field px-1.5 py-0.5 bg-success-subtle text-success"
                ><span class="sr-only">, walidator </span>{{ formatLabel(v) }}</span
              >
            }
            @if (initialData()) {
              <span class="text-[11px] rounded-field px-1.5 py-0.5 bg-warning-subtle text-warning"
                ><span class="sr-only">, </span>dane inicjalne</span
              >
            }
            @if (f.readOnly) {
              <span
                class="text-[11px] rounded-field px-1.5 py-0.5 bg-surface-readonly text-fg-muted"
                ><span class="sr-only">, </span>tylko do odczytu</span
              >
            }
          }
          @if (folded()) {
            <span class="font-normal text-fg-muted">· pól: {{ childCount() }}</span>
          }
        </legend>
        @if (folded()) {
          <!-- header only -->
        } @else if (titleEditable()) {
          <div class="flex flex-wrap items-start gap-3">
            <app-text-field
              class="grow basis-64"
              [label]="optionalTitle() ? 'Tytuł (opcjonalnie)' : 'Etykieta'"
              [required]="!optionalTitle()"
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
                  @for (t of types(); track t.value) {
                    <option [value]="t.value" [selected]="t.value === f.type">
                      {{ t.label }}
                    </option>
                  }
                </select>
              </div>
              @if (formatAllowed()) {
                <div class="basis-48">
                  <label [for]="id + '-format'" class="block text-label font-label mb-1.5"
                    >Walidator</label
                  >
                  <select
                    [id]="id + '-format'"
                    class="block w-full text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                    (change)="changeFormat($event)"
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
                    (change)="patch.emit({ required: $any($event.target).checked })"
                  />
                  Wymagane
                </label>
              }
            }
          </div>
          @if (f.type === 'SELECT') {
            <div>
              <label [for]="id + '-source'" class="block text-label font-label mb-1.5"
                >Źródło opcji</label
              >
              <select
                [id]="id + '-source'"
                class="block w-full max-w-md text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                [attr.aria-describedby]="dictionary()?.description ? id + '-source-hint' : null"
                (change)="changeSource($event)"
              >
                <option value="" [selected]="!f.dictionaryName">Własne opcje</option>
                @for (d of dictionaryChoices(); track d.name) {
                  <option [value]="d.name" [selected]="d.name === f.dictionaryName">
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
              @if (dictionary()?.description; as text) {
                <small [id]="id + '-source-hint'" class="block text-fg-muted mt-1">{{
                  text
                }}</small>
              }
            </div>
          }
          @if (content()) {
            <div>
              <label [for]="id + '-content'" class="block text-label font-label"
                >Treść<span class="text-danger" aria-hidden="true"> *</span></label
              >
              <small [id]="id + '-content-hint'" class="block text-fg-muted mb-1.5"
                >Akapity oddziel pustą linią. Zmieniona treść zastępuje formatowanie i linki z
                dokumentu zwykłym tekstem.</small
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
                (change)="commitContent($event)"
              ></textarea>
              @if (contentErr(); as text) {
                <small [id]="id + '-content-error'" class="block text-danger"
                  ><span aria-hidden="true">✕</span> {{ text }}</small
                >
              }
            </div>
          }
          @if (consent()) {
            <app-consents-editor [value]="consents()" (changed)="commitConsents($event)" />
            <label class="flex items-center gap-2">
              <input
                type="checkbox"
                class="focus-ring"
                [checked]="!!f.consentSectionConfig?.required"
                (change)="patch.emit({ consentsRequired: $any($event.target).checked })"
              />
              Zgody wymagane
            </label>
            <div>
              <label [for]="id + '-files'" class="block text-label font-label">Pliki zgody</label>
              <small [id]="id + '-files-hint'" class="block text-fg-muted mb-1.5"
                >Nazwy plików do pobrania na formularzu, jedna w wierszu.</small
              >
              <textarea
                [id]="id + '-files'"
                rows="2"
                class="block w-full text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                [attr.aria-describedby]="id + '-files-hint'"
                [value]="filesText()"
                (change)="commitFiles($event)"
              ></textarea>
            </div>
          }
          @if (editable() && choice()) {
            @if (f.dictionaryName && f.type !== 'SELECT') {
              <p class="text-fg-muted">Opcje ze słownika {{ f.dictionaryName }}.</p>
            } @else if (!f.dictionaryName) {
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
          <app-field-settings
            [field]="f"
            [taken]="taken()"
            (patch)="patch.emit($event)"
            (rename)="rename.emit($event)"
          />
        } @else {
          <p class="text-fg-muted">Element nieznanego typu — można go tylko usunąć.</p>
        }
        <div class="flex flex-wrap items-center justify-end gap-2" [hidden]="folded()">
          @if (!removable()) {
            <p class="text-fg-muted">Jedynego elementu strony nie można usunąć.</p>
          } @else if (confirming()) {
            <p [id]="id + '-confirm'" class="mr-auto">
              Usunąć „{{ f.title || typeName() }}”{{
                hasChildren() ? ' razem z polami sekcji' : ''
              }}?
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
            <button appButton type="button" variant="ghost" class="remove" (click)="askRemove()">
              Usuń<span class="sr-only"> {{ f.title || typeName() }}</span>
            </button>
          }
        </div>
      </fieldset>
      @if (section()) {
        <button
          appButton
          type="button"
          variant="ghost"
          class="fold shrink-0 self-start mr-1.5 !px-2 !py-0.5"
          [class]="folded() ? 'mt-1.5' : 'mt-2.5'"
          [attr.aria-expanded]="!folded()"
          (click)="toggleFold.emit()"
        >
          <span aria-hidden="true">{{ folded() ? '▸' : '▾' }}</span>
          {{ folded() ? 'Rozwiń' : 'Zwiń'
          }}<span class="sr-only"> {{ f.title || typeName() }}</span>
        </button>
      }
    </div>
  `,
  host: { class: 'block', '[attr.id]': "'edit-field-' + field().id" },
})
export class FieldRow {
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly field = input.required<FormField>();
  readonly removable = input(true);
  /** First / last among its siblings: the arrow key past that end does nothing. */
  readonly first = input(false);
  readonly last = input(false);
  /** Shown faded while it is being dragged. */
  readonly dragging = input(false);
  /** Section shown as its header only. */
  readonly folded = input(false);
  readonly toggleFold = output<void>();
  /** Types offered in "Typ pola" (e.g. only INFO_SECTION on the finish page); null = all. */
  readonly allowedTypes = input<readonly EditableType[] | null>(null);
  readonly patch = output<FieldPatch>();
  /** New techName (the editor also updates conditions that refer to the old one). */
  readonly rename = output<string>();
  /** techNames used in the whole form, for the uniqueness check. */
  readonly taken = input<ReadonlySet<string>>(new Set());
  readonly move = output<-1 | 1>();
  readonly remove = output<void>();

  private static nextId = 0;
  protected readonly id = `field-row-${FieldRow.nextId++}`;
  /** The current type always stays in the list, so the select shows it. */
  protected readonly types = computed(() => {
    const allowed = this.allowedTypes();
    return Object.entries(EDITABLE_TYPES)
      .map(([value, label]) => ({ value: value as EditableType, label }))
      .filter((t) => !allowed || allowed.includes(t.value) || t.value === this.field().type);
  });
  private readonly catalog = inject(SelectDictionaries);
  private readonly dictionaries = this.catalog.list;
  protected readonly proposed = this.catalog.proposed;
  protected readonly PROPOSED = PROPOSED_PREFIX;

  protected readonly section = computed(() => isSection(this.field()));
  protected readonly movable = computed(() => !(this.first() && this.last()));
  protected readonly handleClass = computed(() =>
    !this.movable()
      ? 'bg-surface-readonly text-border'
      : this.section()
        ? 'bg-topbar text-on-topbar cursor-grab active:cursor-grabbing'
        : 'bg-bg text-fg-muted cursor-grab active:cursor-grabbing hover:bg-primary-subtle hover:text-primary',
  );
  protected readonly typeName = computed(() => typeLabel(this.field().type));
  protected readonly initialData = computed(
    () => this.field().defaultValueType === EXTERNAL_SYSTEM,
  );
  protected readonly editable = computed(() => isEditableType(this.field().type));
  protected readonly titleEditable = computed(() => this.editable() || isSection(this.field()));
  protected readonly choice = computed(() => isChoice(this.field().type));
  protected readonly content = computed(() => isContent(this.field().type));
  protected readonly consent = computed(() => isConsent(this.field().type));
  protected readonly inputType = computed(() => takesValue(this.field().type));
  protected readonly formatAllowed = computed(() => takesFormat(this.field().type));
  protected readonly format = computed(() => formatOf(this.field()));
  protected readonly formats = Object.entries(FORMAT_VALIDATORS).map(([value, label]) => ({
    value: value as FormatValidator,
    label,
  }));
  protected readonly formatLabel = (v: FormatValidator) => FORMAT_VALIDATORS[v];
  protected readonly optionalTitle = computed(() => titleOptional(this.field().type));
  protected readonly contentText = computed(() => htmlToText(this.field().description));
  protected readonly consents = computed<ConsentInput[]>(() =>
    (this.field().consentSectionConfig?.consents ?? []).map((c) => ({
      text: htmlToText(c.description),
    })),
  );
  protected readonly filesText = computed(() =>
    (this.field().consentSectionConfig?.files ?? []).join('\n'),
  );
  /** Known dictionaries plus the field's own one when the list could not load or lacks it. */
  protected readonly dictionaryChoices = computed<SelectDictionary[]>(() => {
    const f = this.field();
    const list = this.dictionaries();
    return f.dictionaryName && !list.some((d) => d.name === f.dictionaryName)
      ? [...list, { name: f.dictionaryName, description: '' }]
      : list;
  });
  protected readonly dictionary = computed(() =>
    this.dictionaryChoices().find((d) => d.name === this.field().dictionaryName),
  );
  protected readonly required = computed(
    () => this.field().validation?.includes('REQUIRED') ?? false,
  );
  protected readonly childCount = computed(() => this.field().repeatingSectionGrid?.length ?? 0);
  protected readonly hasChildren = computed(() => this.childCount() > 0);
  protected readonly optionsText = computed(() =>
    (this.field().options ?? []).map((o) => o.name).join('\n'),
  );
  protected readonly titleError = signal<string | null>(null);
  protected readonly optionsErr = signal<string | null>(null);
  protected readonly contentErr = signal<string | null>(null);
  protected readonly confirming = signal(false);

  protected commitTitle(event: Event): void {
    const title = (event.target as HTMLInputElement).value.trim();
    const missing = !title && !this.optionalTitle();
    this.titleError.set(missing ? 'Podaj etykietę pola.' : null);
    if (!missing && title !== this.field().title) this.patch.emit({ title });
  }

  protected changeType(event: Event): void {
    this.optionsErr.set(null);
    this.contentErr.set(null);
    this.titleError.set(null);
    this.patch.emit({ type: (event.target as HTMLSelectElement).value as EditableType });
  }

  protected changeFormat(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.patch.emit({ format: value ? (value as FormatValidator) : null });
  }

  protected changeSource(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const name = select.value;
    this.optionsErr.set(null);
    if (name.startsWith(PROPOSED_PREFIX)) {
      const proposal = this.proposed().find((d) => PROPOSED_PREFIX + d.name === name);
      // The field keeps own options, so the select goes back to "Własne opcje".
      select.value = '';
      if (proposal)
        this.patch.emit({ dictionary: null, options: proposal.items, optionsFrom: proposal.title });
      return;
    }
    const chosen = this.dictionaryChoices().find((d) => d.name === name);
    this.patch.emit({
      dictionary: chosen ? { name: chosen.name } : null,
    });
  }

  protected commitContent(event: Event): void {
    const text = (event.target as HTMLTextAreaElement).value.trim();
    this.contentErr.set(text ? null : 'Podaj treść.');
    if (text && text !== this.contentText()) this.patch.emit({ content: text });
  }

  /** Saved only when every consent has text; the editor shows the error otherwise. */
  protected commitConsents(consents: ConsentInput[]): void {
    if (consents.every((c) => c.text.trim())) this.patch.emit({ consents });
  }

  protected commitFiles(event: Event): void {
    const files = parseOptions((event.target as HTMLTextAreaElement).value);
    if (files.join('\n') !== this.filesText()) this.patch.emit({ consentFiles: files });
  }

  protected commitOptions(event: Event): void {
    const options = parseOptions((event.target as HTMLTextAreaElement).value);
    const error = optionsError(this.field().type, options);
    this.optionsErr.set(error);
    if (!error) this.patch.emit({ options });
  }

  protected onHandleKey(event: KeyboardEvent): void {
    const offset = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0;
    if (!offset || !this.movable()) return;
    event.preventDefault();
    if (offset < 0 ? !this.first() : !this.last()) this.move.emit(offset);
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
