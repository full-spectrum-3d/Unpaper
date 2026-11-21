import { filterOptions, foldText } from './matches';

describe('foldText', () => {
  it('lower-cases and strips diacritics', () => {
    expect(foldText('Łódź')).toBe('lodz');
    expect(foldText('ŚLĄSKIE')).toBe('slaskie');
  });
});

describe('filterOptions', () => {
  const options = ['Łódź', 'Lublin', 'śląskie'];

  it('matches ignoring case and diacritics', () => {
    expect(filterOptions(options, 'lodz')).toEqual(['Łódź']);
    expect(filterOptions(options, 'LÓDŹ')).toEqual(['Łódź']);
    expect(filterOptions(options, 'slask')).toEqual(['śląskie']);
  });

  it('returns all options for an empty query', () => {
    expect(filterOptions(options, '')).toEqual(options);
  });

  it('matches substrings', () => {
    expect(filterOptions(options, 'ub')).toEqual(['Lublin']);
  });

  it('ranks prefix matches before other matches, keeping order', () => {
    expect(filterOptions(['Korea Południowa', 'Polska', 'Nepal', 'Polinezja'], 'pol')).toEqual([
      'Polska',
      'Polinezja',
      'Korea Południowa',
    ]);
  });
});
