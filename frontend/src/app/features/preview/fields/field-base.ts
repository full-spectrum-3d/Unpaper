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
  protected readonly id = computed(() => 'fld-' + this.field().id);
  protected readonly descId = computed(() => this.id() + '-desc');
  // Computed so the DOMParser runs once per field change, not on every render.
  protected readonly hasDescription = computed(() => hasText(this.field().description));
  protected readonly descriptionText = computed(() =>
    this.hasDescription()
      ? new DOMParser()
          .parseFromString(this.field().description!, 'text/html')
          .body.textContent!.trim()
      : undefined,
  );
  /** Id of the description element when there is one, for aria-describedby. */
  protected readonly describedBy = computed(() => (this.hasDescription() ? this.descId() : null));
  protected readonly hasTitle = computed(() => !!this.field().title?.trim());
  protected readonly label = computed(
    () => this.field().title?.trim() || humanize(this.field().techName) || 'Pole bez nazwy',
  );
  /** A fallback label (no title) stays for screen readers only. */
  protected readonly labelClass = computed(() =>
    this.hasTitle() ? 'block text-label font-label mb-1.5' : 'sr-only',
  );
  protected set(v: T) {
    this.answer().set(v);
  }
}

const humanize = (s: string | undefined) => {
  const t = (s ?? '').replace(/[_-]+/g, ' ').trim();
  return t && t[0].toUpperCase() + t.slice(1);
};
