import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-textarea-field',
  imports: [FieldLabel],
  template: `
    <app-field-label
      [label]="label()"
      [for]="id()"
      [hidden]="!hasTitle()"
      [tooltip]="tooltip()"
      [tag]="tag()"
      [required]="required()"
    />
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <textarea
      class="min-h-32"
      [class]="controlClass()"
      [id]="id()"
      rows="5"
      [maxLength]="max"
      [readOnly]="readOnly()"
      [attr.aria-required]="required() || null"
      [attr.aria-describedby]="describedByAll()"
      [attr.aria-invalid]="error() ? 'true' : null"
      [value]="value()"
      (input)="set($any($event.target).value)"
    ></textarea>
    <small [id]="id() + '-count'" class="block text-right text-fg-muted"
      >{{ value().length }}/{{ max }}</small
    >
    <!-- Changes only when a threshold is crossed, so it is announced once, not on every keystroke. -->
    <p class="sr-only" aria-live="polite">{{ limitNotice() }}</p>
    @if (error(); as text) {
      <small [id]="errorId()" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
  `,
  host: { class: 'block' },
})
export class TextareaField extends FieldBase {
  protected readonly max = 8000;
  protected readonly limitNotice = computed(() => {
    const left = this.max - this.value().length;
    if (left <= 0) return `Osiągnięto limit ${this.max} znaków`;
    return left < 200 ? 'Zostało mniej niż 200 znaków' : '';
  });
  protected readonly describedByAll = computed(() =>
    [this.describedBy(), this.id() + '-count'].filter(Boolean).join(' '),
  );
}
