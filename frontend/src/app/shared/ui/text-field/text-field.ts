import { Component, computed, input, model } from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';

let nextId = 0;

@Component({
  selector: 'app-text-field',
  template: `
    <label
      [for]="inputId"
      [class]="labelHidden() ? 'sr-only' : 'block text-label font-label mb-1.5'"
      >{{ label() }}</label
    >
    @if (description(); as text) {
      <small [id]="descriptionId" class="block text-fg-muted">{{ text }}</small>
    }
    <input
      class="block w-full text-fg text-body border rounded-field px-field-x py-field-y focus-ring"
      [class]="
        readonly()
          ? 'border-transparent bg-surface-readonly'
          : (error() ? 'border-danger' : 'border-border-input') + ' bg-surface'
      "
      [readOnly]="readonly()"
      [id]="inputId"
      [type]="type()"
      [value]="value()"
      [attr.autocomplete]="autocomplete()"
      [attr.inputmode]="inputmode()"
      [attr.aria-describedby]="describedBy()"
      [attr.aria-required]="required() || null"
      [attr.aria-invalid]="error() ? 'true' : null"
      (input)="value.set($any($event.target).value)"
    />
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

  private static readonly prefix = 'app-text-field-';
  protected readonly inputId = `${TextField.prefix}${nextId++}`;
  protected readonly descriptionId = `${this.inputId}-description`;
  protected readonly errorId = `${this.inputId}-error`;
  protected readonly describedBy = computed(
    () =>
      [this.description() && this.descriptionId, this.error() && this.errorId]
        .filter(Boolean)
        .join(' ') || null,
  );
}
