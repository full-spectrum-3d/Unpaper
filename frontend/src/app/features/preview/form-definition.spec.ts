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
});
