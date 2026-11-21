import { Injectable, Signal, WritableSignal, signal } from '@angular/core';
import { FormField } from './form-definition';
import { SAMPLE_REGISTRY_DATA } from './sample-registry-data';

export function initialAnswer(field: FormField): unknown {
  const dv = field.defaultValue;
  if (field.type === 'CONSENT_SECTION')
    return (field.consentSectionConfig?.consents ?? []).map(() => false);
  if (field.type === 'CHECKBOX' || field.type === 'FILE_UPLOADER') {
    return field.type === 'CHECKBOX' && dv ? [dv].flat() : [];
  }
  const first = Array.isArray(dv) ? dv[0] : dv;
  if (!first) return '';
  return field.defaultValueType === 'EXTERNAL_SYSTEM' ? (SAMPLE_REGISTRY_DATA[first] ?? '') : first;
}

/** Component-level provider: one signal per field id, created lazily. */
@Injectable()
export class AnswersStore {
  private readonly entries = new Map<
    string,
    { sig: WritableSignal<unknown>; field: FormField; rawSet: (v: unknown) => void }
  >();
  private readonly versionSignal = signal(0);
  readonly version: Signal<number> = this.versionSignal.asReadonly();

  answer(field: FormField): WritableSignal<unknown> {
    let entry = this.entries.get(field.id);
    if (!entry) {
      const sig = signal<unknown>(initialAnswer(field));
      const rawSet = sig.set.bind(sig);
      // Wrapping set/update keeps `version` in sync without effects or subscriptions.
      sig.set = (v) => {
        rawSet(v);
        this.versionSignal.update((n) => n + 1);
      };
      sig.update = (fn) => sig.set(fn(sig()));
      entry = { sig, field, rawSet };
      this.entries.set(field.id, entry);
    }
    return entry.sig;
  }

  reset(): void {
    this.entries.forEach((e) => e.rawSet(initialAnswer(e.field)));
    this.versionSignal.update((n) => n + 1);
  }

  snapshot(): ReadonlyMap<string, unknown> {
    return new Map([...this.entries].map(([id, e]) => [id, e.sig()]));
  }
}
