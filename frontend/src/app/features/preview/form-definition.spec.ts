import nadplata from '../import/mock-forms/nadplata-podatku.json';
import numer from '../import/mock-forms/numer-porzadkowy.json';
import { isFormDefinition } from './form-definition';

describe('isFormDefinition', () => {
  it('accepts reference forms', () => {
    expect(isFormDefinition(nadplata)).toBe(true);
    expect(isFormDefinition(numer)).toBe(true);
  });

  it('rejects non-form results', () => {
    for (const v of [null, {}, [], 'x', { title: 'a', tabs: {} }, { title: 'a', tabs: [{}] }]) {
      expect(isFormDefinition(v)).toBe(false);
    }
  });

  it('rejects malformed questions at any depth', () => {
    const form = (field: unknown) => ({
      title: 'a',
      tabs: [{ questions: [{ x: 0, y: 0, rows: 1, cols: 1, field }] }],
    });
    const ok = { id: 'f', type: 'TEXT_FIELD', title: 'T', techName: 't' };
    expect(isFormDefinition(form(ok))).toBe(true);
    expect(isFormDefinition(form({ ...ok, states: null, repeatingSectionGrid: null }))).toBe(true);
    for (const field of [
      undefined,
      { type: 'TEXT_FIELD' },
      { ...ok, id: 1 },
      { ...ok, title: 5 },
      { ...ok, states: 'x' },
      { ...ok, states: [null] },
      { ...ok, options: [{ id: 'a' }] },
      { ...ok, repeatingSectionGrid: {} },
      { ...ok, repeatingSectionGrid: [{ field: { id: 'inner' } }] },
    ]) {
      expect(isFormDefinition(form(field)), JSON.stringify(field)).toBe(false);
    }
  });
});
