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
  it('is true for TERYT dictionaries regardless of multiLevelTree', () => {
    expect(isCascade(f({ dictionaryName: 'TERYT_4G_DOWODOWY' }))).toBe(true);
    expect(isCascade(f({ dictionaryName: 'TERYT_DOWODOWY', multiLevelTree: false }))).toBe(true);
  });
  it('is false for single-level dictionaries and fields with options', () => {
    expect(isCascade(f({ dictionaryName: 'Kraje' }))).toBe(false);
    expect(
      isCascade(f({ dictionaryName: 'TERYT_DOWODOWY', options: [{ id: '1', name: 'A' }] })),
    ).toBe(false);
  });
});

describe('isSearchable', () => {
  it('follows searchEnabled or more than 20 options', () => {
    expect(isSearchable(f({ searchEnabled: true }), 3)).toBe(true);
    expect(isSearchable(f({ searchEnabled: null }), 21)).toBe(true);
    expect(isSearchable(f({}), 20)).toBe(false);
  });
});
