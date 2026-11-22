import {
  afterRenderEffect,
  Component,
  computed,
  DOCUMENT,
  effect,
  ElementRef,
  inject,
  input,
  model,
  signal,
} from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';
import { FieldTooltip } from '../field-tooltip/field-tooltip';
import { filterOptions } from './matches';

let nextId = 0;
const MAX_VISIBLE = 200;

@Component({
  selector: 'app-combobox',
  imports: [FieldTooltip],
  template: `
    <div [class]="labelHidden() ? 'contents' : 'flex flex-wrap items-center gap-x-2 mb-1.5'">
      <label [for]="inputId" [class]="labelHidden() ? 'sr-only' : 'text-label font-label'"
        >{{ label() }}<span class="sr-only">{{ tag() ? ', ' + tag() : '' }}</span>
      </label>
      <!-- Outside the label: visual only (aria-required carries it), and label text stays clean. -->
      @if (required() && !labelHidden()) {
        <span class="text-danger -ml-1.5" aria-hidden="true">*</span>
      }
      @if (tooltip(); as text) {
        <app-field-tooltip [text]="text" [label]="label()" />
      }
      @if (tag(); as text) {
        <span class="ml-auto text-fg-muted text-label font-normal" aria-hidden="true">{{
          text
        }}</span>
      }
    </div>
    <ng-content select="[description]" />
    <div class="relative">
      <input
        #field
        role="combobox"
        autocomplete="off"
        class="block w-full text-fg text-body border rounded-field px-field-x py-field-y pr-16 focus-ring"
        [class]="
          readonly()
            ? 'border-dashed border-border-input bg-surface-readonly'
            : (error() ? 'border-danger' : 'border-border-input') +
              ' bg-surface' +
              (searchable() ? '' : ' caret-transparent cursor-pointer')
        "
        [id]="inputId"
        [readOnly]="readonly()"
        [attr.inputmode]="searchable() ? null : 'none'"
        [placeholder]="placeholder()"
        [value]="open() && searchable() ? query() : value()"
        [attr.aria-autocomplete]="searchable() ? 'list' : null"
        [attr.aria-expanded]="open()"
        [attr.aria-controls]="listboxId"
        [attr.aria-activedescendant]="open() && visible().length ? optionId(active()) : null"
        [attr.aria-describedby]="describedByIds()"
        [attr.aria-invalid]="error() ? 'true' : null"
        [attr.aria-required]="required() || null"
        (click)="show()"
        (keydown)="onKey($event)"
        (beforeinput)="searchable() || $event.preventDefault()"
        (input)="onInput($any($event.target).value)"
        (blur)="close()"
      />
      <div class="absolute inset-y-0 right-2 flex items-center gap-1">
        @if (value() && !readonly()) {
          <button
            type="button"
            class="p-1 rounded-field text-fg-muted focus-ring"
            [attr.aria-label]="'Wyczyść: ' + label()"
            (click)="clear(field)"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              class="size-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        }
        @if (!readonly()) {
          <svg
            aria-hidden="true"
            viewBox="0 0 16 16"
            class="size-4 text-fg-muted cursor-pointer"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            (click)="field.focus(); show()"
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        }
      </div>
      <ul
        role="listbox"
        class="absolute z-10 mt-1 w-full max-h-64 overflow-auto bg-surface border border-border-input rounded-field"
        [id]="listboxId"
        [attr.aria-label]="label()"
        [hidden]="!open() || !visible().length"
        (pointerdown)="$event.preventDefault()"
      >
        @if (open()) {
          <!-- Options come from imported JSON: duplicates are possible, so track by position. -->
          @for (option of visible(); track $index; let i = $index) {
            <li
              role="option"
              class="flex items-center gap-2 px-field-x py-field-y text-body cursor-pointer"
              [class]="i === active() ? 'bg-primary text-on-primary' : 'text-fg'"
              [id]="optionId(i)"
              [attr.aria-selected]="option === value()"
              (click)="select(option)"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 16 16"
                class="size-4 shrink-0"
                [class.invisible]="option !== value()"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M3 8.5l3 3 7-7" />
              </svg>
              {{ option }}
            </li>
          }
          @if (truncated()) {
            <li role="presentation" class="px-field-x py-field-y text-body text-fg-muted">
              Wpisz więcej liter, aby zawęzić listę
            </li>
          }
        }
      </ul>
      <!-- Always in the DOM: live regions inserted with text are not reliably announced. -->
      <p role="status" class="sr-only">{{ open() && !visible().length ? emptyText() : '' }}</p>
      @if (open() && !visible().length) {
        <p
          aria-hidden="true"
          class="absolute z-10 mt-1 w-full bg-surface border border-border-input rounded-field px-field-x py-field-y text-body text-fg-muted"
        >
          {{ emptyText() }}
        </p>
      }
    </div>
    @if (error(); as text) {
      <small [id]="errorId" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
  `,
  host: { class: 'block' },
})
export class Combobox implements FormValueControl<string> {
  readonly value = model('');
  readonly options = input.required<readonly string[]>();
  readonly label = input.required<string>();
  readonly labelHidden = input(false);
  readonly searchable = input(false);
  readonly placeholder = input('Wybierz');
  readonly describedBy = input<string | null>(null);
  readonly emptyText = input('Brak wyników');
  readonly error = input<string>();
  readonly readonly = input(false);
  readonly required = input(false);
  readonly tooltip = input<string>();
  readonly tag = input<string>();

  readonly inputId = `app-combobox-${nextId++}`;
  protected readonly listboxId = `${this.inputId}-listbox`;
  protected readonly errorId = `${this.inputId}-error`;
  protected readonly describedByIds = computed(
    () => [this.describedBy(), this.error() && this.errorId].filter(Boolean).join(' ') || null,
  );

  protected readonly open = signal(false);
  protected readonly query = signal('');
  protected readonly active = signal(0);
  private readonly matching = computed(() =>
    this.searchable() ? filterOptions(this.options(), this.query()) : this.options(),
  );
  /** Rendering tens of thousands of options (e.g. all localities) would freeze the page. */
  protected readonly visible = computed(() => this.matching().slice(0, MAX_VISIBLE));
  protected readonly truncated = computed(() => this.matching().length > MAX_VISIBLE);

  private readonly host = inject(ElementRef<HTMLElement>).nativeElement as HTMLElement;
  private readonly document = inject(DOCUMENT);
  /** Letters typed in select-only mode, cleared after a pause (listbox typeahead). */
  private typed = '';
  private typedAt = 0;

  constructor() {
    // Listen for outside pointerdown only while open: one document listener per open list, not per instance.
    effect((onCleanup) => {
      if (!this.open()) return;
      const onPointer = (event: Event) => {
        if (!this.host.contains(event.target as Node)) this.close();
      };
      this.document.addEventListener('pointerdown', onPointer);
      onCleanup(() => this.document.removeEventListener('pointerdown', onPointer));
    });
    afterRenderEffect(() => {
      if (this.open()) {
        this.host
          .querySelector(`#${this.optionId(this.active())}`)
          ?.scrollIntoView?.({ block: 'nearest' });
      }
    });
  }

  protected optionId(i: number): string {
    return `${this.listboxId}-${i}`;
  }

  protected show(): void {
    if (this.open() || this.readonly()) return;
    this.active.set(Math.max(0, this.visible().indexOf(this.value())));
    this.open.set(true);
  }

  protected close(): void {
    this.open.set(false);
    this.query.set('');
  }

  protected select(option: string): void {
    this.value.set(option);
    this.close();
  }

  protected clear(field: HTMLInputElement): void {
    this.value.set('');
    field.focus();
  }

  protected onInput(text: string): void {
    this.query.set(text);
    this.active.set(0);
    this.open.set(true);
  }

  protected onKey(event: KeyboardEvent): void {
    const last = this.visible().length - 1;
    const move = (i: number) => this.active.set(Math.min(Math.max(i, 0), Math.max(last, 0)));
    if (this.readonly()) return;
    if (!this.searchable() && this.isTypeahead(event)) {
      event.preventDefault();
      this.show();
      this.typeahead(event.key);
      return;
    }
    if (!this.open()) {
      const opens =
        ['ArrowDown', 'ArrowUp'].includes(event.key) ||
        (!this.searchable() && (event.key === 'Enter' || event.key === ' '));
      if (opens) {
        event.preventDefault();
        this.show();
      }
      return;
    }
    switch (event.key) {
      case 'ArrowDown':
        move(this.active() + 1);
        break;
      case 'ArrowUp':
        move(this.active() - 1);
        break;
      // In the searchable input Home/End move the caret; they move the list only in select-only mode.
      case 'Home':
        if (this.searchable()) return;
        move(0);
        break;
      case 'End':
        if (this.searchable()) return;
        move(last);
        break;
      case 'Enter': {
        const option = this.visible()[this.active()];
        if (option !== undefined) this.select(option);
        break;
      }
      case 'Escape':
        this.close();
        break;
      default:
        return;
    }
    event.preventDefault();
  }

  private isTypeahead(event: KeyboardEvent): boolean {
    return (
      event.key.length === 1 &&
      event.key !== ' ' &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey
    );
  }

  /** Moves to the next option starting with the typed letters; repeating one letter cycles through matches. */
  private typeahead(key: string): void {
    const now = Date.now();
    this.typed = now - this.typedAt > 500 ? key : this.typed + key;
    this.typedAt = now;
    const prefix = this.typed.toLocaleLowerCase('pl');
    const cycling = [...prefix].every((c) => c === prefix[0]);
    const options = this.visible();
    // A fresh or repeated single letter starts after the active option; a longer prefix may stay on it.
    const start = cycling ? this.active() + 1 : this.active();
    for (let k = 0; k < options.length; k++) {
      const i = (start + k) % options.length;
      const name = options[i].toLocaleLowerCase('pl');
      if (name.startsWith(cycling ? prefix[0] : prefix)) {
        this.active.set(i);
        return;
      }
    }
  }
}
