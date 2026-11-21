import { Directive, computed, inject, input } from '@angular/core';
import { FormField } from '../form-definition';
import { AnswersStore } from '../answers-store';
import { hasText } from '../html-text';

/** Shared plumbing: the field input, its answer signal and the empty-description check. */
@Directive()
export abstract class FieldBase<T = string> {
  readonly field = input.required<FormField>();
  protected readonly store = inject(AnswersStore);
  // Call expressions are not allowed in two-way bindings, so bind one-way via this signal.
  protected readonly answer = computed(() => this.store.answer(this.field()));
  protected readonly value = computed(() => this.answer()() as T);
  protected readonly hasText = hasText;
  protected set(v: T) {
    this.answer().set(v);
  }
}
