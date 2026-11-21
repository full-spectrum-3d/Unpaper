import { Component, computed, input, model } from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';

let nextId = 0;

@Component({
  selector: 'app-text-field',
  template: `
    <label [for]="inputId" class="block text-label font-semibold">{{ label() }}</label>
    @if (description(); as text) {
      <small [id]="descriptionId" class="block text-fg-muted">{{ text }}</small>
    }
    <input
      class="block w-full bg-surface text-fg text-body border rounded-field px-field-x py-field-y focus-ring"
      [class]="error() ? 'border-danger' : 'border-border-input'"
      [id]="inputId"
      [type]="type()"
      [value]="value()"
      [attr.autocomplete]="autocomplete()"
      [attr.aria-describedby]="describedBy()"
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
  readonly error = input<string>();
  readonly autocomplete = input<string>();

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
