import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { mockReport } from '../import/mock-report';
import { formatJson } from './json-lines';
import { asReport, formatSeconds, pathTarget } from './report';

describe('asReport', () => {
  it('returns the same object with list fields always arrays', () => {
    const r = { warnings: 'x', fixes: [{ code: 'A', message: 'm' }], stats: null };
    const out = asReport(r)!;
    expect(out).toBe(r);
    expect(out.warnings).toEqual([]);
    expect(out.fixes).toHaveLength(1);
    expect(out.dictionaryProposals).toEqual([]);
  });

  it('rejects non-objects', () => {
    for (const v of [null, 'x', [], 1, undefined]) expect(asReport(v)).toBeNull();
  });
});

describe('pathTarget', () => {
  const { ranges } = formatJson(nadplata);
  const issue = (path?: string, code = 'W01') => ({ code, message: 'm', path });

  it('decides link, draft, missing and none', () => {
    expect(pathTarget(issue(), ranges)).toEqual({ kind: 'none' });
    expect(pathTarget(issue('subject_pages[0].sections[0].fields[0]'), ranges)).toEqual({ kind: 'draft' });
    expect(pathTarget(issue('title'), ranges)).toEqual({ kind: 'draft' });
    expect(pathTarget(issue('tabs[0]'), ranges)).toEqual({ kind: 'link' });
    expect(pathTarget(issue('tabs[9]'), ranges)).toEqual({ kind: 'missing' });
    expect(pathTarget(issue('tabs[0]', 'R03_EMPTY_PAGE'), ranges)).toEqual({ kind: 'missing' });
  });

  it('links every tabs path of the mock report that exists', () => {
    const r = asReport(mockReport(nadplata))!;
    expect(pathTarget(r.warnings![1], ranges).kind).toBe('link');
  });
});

describe('formatSeconds', () => {
  it('uses one decimal and a comma', () => {
    expect(formatSeconds(25110)).toBe('25,1 s');
    expect(formatSeconds(140)).toBe('0,1 s');
    expect(formatSeconds(0)).toBe('0,0 s');
  });
});
