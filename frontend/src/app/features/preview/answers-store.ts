import { Injectable, Signal, WritableSignal, signal } from '@angular/core';
import { FormDefinition, FormField, Question } from './form-definition';
import { SAMPLE_REGISTRY_DATA } from './sample-registry-data';
import { isCascade } from './select-options';

export function initialAnswer(field: FormField): unknown {
  const dv = field.defaultValue;
  if (field.type === 'CONSENT_SECTION')
    return (field.consentSectionConfig?.consents ?? []).map(() => false);
  if (field.type === 'CHECKBOX' || field.type === 'FILE_UPLOADER') {
    return field.type === 'CHECKBOX' && dv ? [dv].flat() : [];
  }
  if (isCascade(field)) return [dv ?? []].flat().filter(Boolean);
  // Imported JSON is untrusted: a numeric or boolean default must still become text (0 included).
  const raw: unknown = Array.isArray(dv) ? dv[0] : dv;
  if (raw == null || typeof raw === 'object') return '';
  const first = String(raw);
  const value =
    field.defaultValueType === 'EXTERNAL_SYSTEM' ? (SAMPLE_REGISTRY_DATA[first] ?? '') : first;
  return field.type === 'DATEPICKER' ? toIsoDate(value) : value;
}

/**
 * Value for <input type=date>: yyyy-mm-dd. Accepts dd.mm.yyyy (also with / or -) and ISO date-times;
 * anything else is cleared, as the input would show it blank while REQUIRED counted it as filled.
 */
export function toIsoDate(text: string): string {
  const t = text.trim();
  const iso = /^(\d{4}-\d{2}-\d{2})(?:[T ].*)?$/.exec(t);
  const pl = /^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/.exec(t);
  const date = iso
    ? iso[1]
    : pl
      ? `${pl[3]}-${pl[2].padStart(2, '0')}-${pl[1].padStart(2, '0')}`
      : '';
  // Reject impossible dates such as 2024-02-31: Date would roll them over.
  const d = new Date(date + 'T00:00:00Z');
  return date && !isNaN(d.getTime()) && d.toISOString().startsWith(date) ? date : '';
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
    return (this.entries.get(field.id) ?? this.create(field)).sig;
  }

  /** Creates entries for every field of every tab, so `snapshot()` is complete; replaces earlier entries. */
  init(def: FormDefinition): void {
    this.entries.clear();
    const visit = (qs: Question[]) =>
      qs.forEach(({ field }) => {
        this.create(field);
        visit(field.repeatingSectionGrid ?? []);
      });
    def.tabs.forEach((t) => visit(t.questions));
    this.versionSignal.update((n) => n + 1);
  }

  private create(field: FormField) {
    const sig = signal<unknown>(initialAnswer(field));
    const rawSet = sig.set.bind(sig);
    // Wrapping set/update keeps `version` in sync without effects or subscriptions.
    sig.set = (v) => {
      rawSet(v);
      this.versionSignal.update((n) => n + 1);
    };
    sig.update = (fn) => sig.set(fn(sig()));
    const entry = { sig, field, rawSet };
    this.entries.set(field.id, entry);
    return entry;
  }

  reset(): void {
    this.entries.forEach((e) => e.rawSet(initialAnswer(e.field)));
    this.versionSignal.update((n) => n + 1);
  }

  snapshot(): ReadonlyMap<string, unknown> {
    return new Map([...this.entries].map(([id, e]) => [id, e.sig()]));
  }
}
