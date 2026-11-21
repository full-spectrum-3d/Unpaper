import { formatSize, pluralPl, queueSummary } from './format';

describe('formatSize', () => {
  it.each([
    [0, '0 B'],
    [86016, '84 KB'],
    [1258291, '1,2 MB'],
  ])('formats %d as %s', (bytes, text) => {
    expect(formatSize(bytes)).toBe(text);
  });
});

describe('pluralPl', () => {
  it.each([
    [1, 'plik'],
    [2, 'pliki'],
    [5, 'plików'],
    [12, 'plików'],
    [22, 'pliki'],
    [25, 'plików'],
  ])('picks form for %d', (n, form) => {
    expect(pluralPl(n, 'plik', 'pliki', 'plików')).toBe(form);
  });
});

describe('queueSummary', () => {
  it('summarizes singular and few forms', () => {
    expect(queueSummary({ total: 4, done: 1, error: 1 })).toBe('4 pliki · 1 gotowy · 1 błąd');
  });

  it('summarizes many forms', () => {
    expect(queueSummary({ total: 5, done: 2, error: 5 })).toBe('5 plików · 2 gotowe · 5 błędów');
  });
});
