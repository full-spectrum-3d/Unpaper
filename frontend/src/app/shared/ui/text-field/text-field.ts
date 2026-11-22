import { Component, computed, input, model, signal } from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';
import { FieldTooltip } from '../field-tooltip/field-tooltip';

let nextId = 0;

@Component({
  selector: 'app-text-field',
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
    @if (description(); as text) {
      <small [id]="descriptionId" class="mb-[6px] block text-fg-muted">{{ text }}</small>
    }
    <div class="relative">
      <input
        class="block w-full text-fg text-body border rounded-field px-field-x py-field-y focus-ring"
        [class]="
          (revealable() ? 'pr-[40px] ' : '') +
          (readonly()
            ? 'border-dashed border-border-input bg-surface-readonly'
            : (error() ? 'border-danger' : 'border-border-input') + ' bg-surface')
        "
        [readOnly]="readonly()"
        [id]="inputId"
        [type]="inputType()"
        [value]="value()"
        [attr.autocomplete]="autocomplete()"
        [attr.inputmode]="inputmode()"
        [attr.aria-describedby]="describedBy()"
        [attr.aria-required]="required() || null"
        [attr.aria-invalid]="error() ? 'true' : null"
        (input)="value.set($any($event.target).value)"
      />
      @if (revealable()) {
        <button
          type="button"
          class="absolute inset-y-0 right-0 flex w-[36px] items-center justify-center rounded-field text-fg-muted hover:text-fg focus-ring"
          aria-label="Pokaż hasło"
          [attr.aria-controls]="inputId"
          [attr.aria-pressed]="revealed()"
          (click)="revealed.set(!revealed())"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
            <circle cx="12" cy="12" r="3" />
            @if (revealed()) {
              <path d="M3 3l18 18" />
            }
          </svg>
        </button>
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
export class TextField implements FormValueControl<string> {
  readonly value = model('');
  readonly label = input.required<string>();
  readonly type = input<'text' | 'password'>('text');
  readonly description = input<string>();
  readonly required = input(false);
  readonly error = input<string>();
  readonly autocomplete = input<string>();
  readonly readonly = input(false);
  readonly labelHidden = input(false);
  readonly inputmode = input<string>();
  readonly tooltip = input<string>();
  readonly tag = input<string>();
  /** Password field with a show/hide toggle. */
  readonly revealable = input(false);

  private static readonly prefix = 'app-text-field-';
  protected readonly inputId = `${TextField.prefix}${nextId++}`;
  protected readonly descriptionId = `${this.inputId}-description`;
  protected readonly errorId = `${this.inputId}-error`;
  protected readonly revealed = signal(false);
  protected readonly inputType = computed(() =>
    this.revealable() && this.revealed() ? 'text' : this.type(),
  );
  protected readonly describedBy = computed(
    () =>
      [this.description() && this.descriptionId, this.error() && this.errorId]
        .filter(Boolean)
        .join(' ') || null,
  );
}
