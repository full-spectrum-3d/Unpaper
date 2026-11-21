import { FormField, Question } from './form-definition';
import { validateStep } from './validate-step';

const q = (field: Partial<FormField> & { id: string }): Question => ({
  x: 0,
  y: 0,
  rows: 1,
  cols: 1,
  field: {
    type: 'TEXT_FIELD',
    techName: field.id,
    title: field.id,
    validation: ['REQUIRED'],
    ...field,
  },
});
const NONE: ReadonlySet<string> = new Set();
const run = (qs: Question[], hidden = NONE, readOnly = NONE) =>
  validateStep(qs, new Map(), hidden, readOnly);

describe('validateStep', () => {
  it('returns errors of required fields on all levels', () => {
    const qs = [
      q({ id: 'a' }),
      q({ id: 's', type: 'SECTION', validation: [], repeatingSectionGrid: [q({ id: 'b' })] }),
    ];
    expect([...run(qs)]).toEqual([
      ['a', 'Uzupełnij to pole'],
      ['b', 'Uzupełnij to pole'],
    ]);
  });

  it('validates against the given answers', () => {
    const qs = [q({ id: 'a' })];
    expect(validateStep(qs, new Map([['a', 'x']]), NONE, NONE).size).toBe(0);
  });

  it('skips hidden ids and descendants of a hidden section', () => {
    const qs = [
      q({ id: 'a' }),
      q({ id: 's', type: 'SECTION', validation: [], repeatingSectionGrid: [q({ id: 'b' })] }),
    ];
    expect(run(qs, new Set(['a', 's'])).size).toBe(0);
  });

  it('skips read-only fields, static and from states', () => {
    const qs = [q({ id: 'a' }), q({ id: 'b', readOnly: true })];
    expect(run(qs, NONE, new Set(['a'])).size).toBe(0);
  });

  it('skips SECTION and TEXT_BLOCK even with REQUIRED', () => {
    const qs = [
      q({ id: 's', type: 'SECTION', repeatingSectionGrid: [] }),
      q({ id: 't', type: 'TEXT_BLOCK' }),
    ];
    expect(run(qs).size).toBe(0);
  });
});
