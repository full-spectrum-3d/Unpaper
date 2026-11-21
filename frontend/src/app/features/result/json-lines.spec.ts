import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { formatJson } from './json-lines';

describe('formatJson', () => {
  it('matches JSON.stringify for the mock form', () => {
    expect(formatJson(nadplata).lines.join('\n')).toBe(JSON.stringify(nadplata, null, 2));
  });

  it('matches JSON.stringify for edge cases', () => {
    const x = { 'a.b': [1, {}, []], 'q"': null, e: {} };
    expect(formatJson(x).lines.join('\n')).toBe(JSON.stringify(x, null, 2));
    for (const v of [[], {}, 'a', 1, null]) {
      expect(formatJson(v).lines.join('\n')).toBe(JSON.stringify(v, null, 2));
    }
  });

  it('follows stringify semantics for undefined', () => {
    const x = { a: undefined, b: [undefined, 1] };
    expect(formatJson(x).lines.join('\n')).toBe(JSON.stringify(x, null, 2));
  });

  it('maps a top-level key to its line', () => {
    const r = formatJson({ title: 'T', tabs: [{ a: 1 }] });
    expect(r.ranges.get('title')).toEqual({ start: 1, end: 1 });
    expect(r.ranges.get('tabs')).toEqual({ start: 2, end: 6 });
    expect(r.ranges.get('tabs[0]')).toEqual({ start: 3, end: 5 });
    expect(r.ranges.get('')).toEqual({ start: 0, end: 7 });
  });

  it('maps tabs and nested values in the mock form', () => {
    const { lines, ranges } = formatJson(nadplata);
    const tab = ranges.get('tabs[0]')!;
    expect(lines[tab.start]).toBe('    {');
    expect(['    }', '    },']).toContain(lines[tab.end]);
    const q = ranges.get('tabs[0].questions[1]')!;
    expect(q.start).toBeGreaterThanOrEqual(tab.start);
    expect(q.end).toBeLessThanOrEqual(tab.end);
    expect(ranges.has('tabs[0].questions[1].field.repeatingSectionGrid[1]')).toBe(true);
    expect(ranges.has('tabs[99]')).toBe(false);
  });

  it('gives empty containers a single line', () => {
    const { ranges } = formatJson({ a: [], b: {} });
    expect(ranges.get('a')).toEqual({ start: 1, end: 1 });
    expect(ranges.get('b')).toEqual({ start: 2, end: 2 });
  });
});
