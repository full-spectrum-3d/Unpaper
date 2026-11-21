import { Injectable, signal } from '@angular/core';
import { FormField } from './form-definition';

/** Per-renderer state the fields read without inputs threaded through the grid; FormRenderer is the only writer. */
@Injectable()
export class FormState {
  readonly readOnly = signal<ReadonlySet<string>>(new Set());
  readonly errors = signal<ReadonlyMap<string, string>>(new Map());

  isReadOnly(field: FormField): boolean {
    return !!field.readOnly || this.readOnly().has(field.id);
  }

  error(field: FormField): string | null {
    return this.errors().get(field.id) ?? null;
  }
}
