import {
  afterRenderEffect,
  Component,
  computed,
  ElementRef,
  inject,
  input,
  model,
  signal,
} from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';
import { filterOptions } from './matches';

let nextId = 0;

@Component({
  selector: 'app-combobox',
  template: `
    <label
      [for]="inputId"
      [class]="labelHidden() ? 'sr-only' : 'block text-label font-label mb-1.5'"
      >{{ label() }}</label
    >
    <ng-content select="[description]" />
    <div class="relative">
      <input
        #field
        role="combobox"
        autocomplete="off"
        class="block w-full bg-surface text-fg text-body border border-border-input rounded-field px-field-x py-field-y pr-16 focus-ring"
        [id]="inputId"
        [readOnly]="!searchable()"
        [placeholder]="placeholder()"
        [value]="open() && searchable() ? query() : value()"
        [attr.aria-autocomplete]="searchable() ? 'list' : null"
        [attr.aria-expanded]="open()"
        [attr.aria-controls]="listboxId"
        [attr.aria-activedescendant]="open() && visible().length ? optionId(active()) : null"
        [attr.aria-describedby]="describedBy()"
        (click)="show()"
        (keydown)="onKey($event)"
        (input)="onInput($any($event.target).value)"
        (blur)="close()"
      />
      <div class="absolute inset-y-0 right-2 flex items-center gap-1">
        @if (value()) {
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
      </div>
      <ul
        role="listbox"
        class="absolute z-10 mt-1 w-full max-h-64 overflow-auto bg-surface border border-border-input rounded-field"
        [id]="listboxId"
        [attr.aria-label]="label()"
        [hidden]="!open() || !visible().length"
      >
        @if (open()) {
          @for (option of visible(); track option; let i = $index) {
            <li
              role="option"
              class="px-field-x py-field-y text-body text-fg cursor-pointer"
              [class.bg-primary-subtle]="i === active()"
              [id]="optionId(i)"
              [attr.aria-selected]="option === value()"
              (pointerdown)="$event.preventDefault()"
              (click)="select(option)"
            >
              {{ option }}
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
  `,
  host: { class: 'block', '(document:pointerdown)': 'onDocPointer($event)' },
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

  readonly inputId = `app-combobox-${nextId++}`;
  protected readonly listboxId = `${this.inputId}-listbox`;

  protected readonly open = signal(false);
  protected readonly query = signal('');
  protected readonly active = signal(0);
  protected readonly visible = computed(() =>
    this.searchable() ? filterOptions(this.options(), this.query()) : this.options(),
  );

  private readonly host = inject(ElementRef<HTMLElement>).nativeElement as HTMLElement;

  constructor() {
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
    if (this.open()) return;
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

  protected onDocPointer(event: Event): void {
    if (!this.host.contains(event.target as Node)) this.close();
  }

  protected onKey(event: KeyboardEvent): void {
    const last = this.visible().length - 1;
    const move = (i: number) => this.active.set(Math.min(Math.max(i, 0), Math.max(last, 0)));
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
      case 'Home':
        move(0);
        break;
      case 'End':
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
}
