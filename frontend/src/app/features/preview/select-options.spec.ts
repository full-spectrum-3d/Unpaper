import { FormField } from './form-definition';
import { isCascade, isSearchable, selectOptions } from './select-options';

const f = (o: Partial<FormField>): FormField => ({
  id: '1',
  type: 'SELECT',
  techName: 't',
  title: 'T',
  ...o,
});

describe('selectOptions', () => {
  it('prefers non-empty options over the dictionary', () => {
    expect(
      selectOptions(f({ options: [{ id: '1', name: 'A' }], dictionaryName: 'Kraje' })),
    ).toEqual(['A']);
  });
  it('falls back to dictionary level 0', () => {
    expect(selectOptions(f({ dictionaryName: 'Kraje' }))).toContain('Polska');
  });
  it('is empty for unknown dictionary', () => {
    expect(selectOptions(f({ dictionaryName: 'Nieznany' }))).toEqual([]);
  });
});

describe('isCascade', () => {
  it('is true for TERYT dictionaries', () => {
    expect(isCascade(f({ dictionaryName: 'TERYT_4G_DOWODOWY' }))).toBe(true);
    expect(isCascade(f({ dictionaryName: 'TERYT_DOWODOWY' }))).toBe(true);
  });
  it('is false for single-level dictionaries and fields with options', () => {
    expect(isCascade(f({ dictionaryName: 'Kraje' }))).toBe(false);
    expect(
      isCascade(f({ dictionaryName: 'TERYT_DOWODOWY', options: [{ id: '1', name: 'A' }] })),
    ).toBe(false);
  });
});

describe('isSearchable', () => {
  it('is true for more than 20 options', () => {
    expect(isSearchable(21)).toBe(true);
    expect(isSearchable(20)).toBe(false);
  });
});
