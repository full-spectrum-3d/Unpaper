import { FormField } from './form-definition';
import { AnswersStore, initialAnswer } from './answers-store';
import { SAMPLE_REGISTRY_DATA } from './sample-registry-data';

const f = (p: Partial<FormField>): FormField => ({
  id: p.type ?? 'x',
  techName: 't',
  title: 'T',
  type: 'TEXT_FIELD',
  ...p,
});

describe('initialAnswer', () => {
  it('derives initial values by type', () => {
    expect(initialAnswer(f({ defaultValue: 'Urząd Gminy Ulan-Majorat' }))).toBe(
      'Urząd Gminy Ulan-Majorat',
    );
    expect(initialAnswer(f({ type: 'SELECT', defaultValue: ['Polska'] }))).toBe('Polska');
    expect(initialAnswer(f({ type: 'SELECT', defaultValue: [] }))).toBe('');
    expect(initialAnswer(f({ type: 'CHECKBOX' }))).toEqual([]);
    expect(
      initialAnswer(
        f({
          type: 'CONSENT_SECTION',
          consentSectionConfig: { consents: [{ description: 'a' }, { description: 'b' }] },
        }),
      ),
    ).toEqual([false, false]);
  });

  it('reads registry data for EXTERNAL_SYSTEM', () => {
    const field = f({ defaultValue: 'PESEL.name', defaultValueType: 'EXTERNAL_SYSTEM' });
    expect(initialAnswer(field)).toBe(SAMPLE_REGISTRY_DATA['PESEL.name']);
    expect(initialAnswer(f({ defaultValue: 'NOPE.x', defaultValueType: 'EXTERNAL_SYSTEM' }))).toBe(
      '',
    );
  });
});

describe('AnswersStore', () => {
  it('version increments on set and update', () => {
    const s = new AnswersStore();
    const sig = s.answer(f({}));
    const v = s.version();
    sig.set('a');
    expect(s.version()).toBe(v + 1);
    sig.update((x) => x + 'b');
    expect(sig()).toBe('ab');
    expect(s.version()).toBe(v + 2);
  });

  it('reset restores initial values', () => {
    const s = new AnswersStore();
    const field = f({ defaultValue: 'x' });
    const sig = s.answer(field);
    sig.set('changed');
    const v = s.version();
    s.reset();
    expect(sig()).toBe('x');
    expect(s.version()).toBeGreaterThan(v);
    expect(s.snapshot().get(field.id)).toBe('x');
  });

  it('answer returns same signal for same field', () => {
    const s = new AnswersStore();
    const field = f({});
    expect(s.answer(field)).toBe(s.answer(field));
  });
});
