import { HttpErrorResponse } from '@angular/common/http';
import { MOCK_DOCUMENT_PASSWORD, mockConvertFile } from './convert-file.mock';

const run = (name: string, password?: string) => {
  const out: { value?: unknown; error?: unknown } = {};
  mockConvertFile(new File(['x'], name), password).subscribe({
    next: (v) => (out.value = v),
    error: (e) => (out.error = e),
  });
  return out;
};

interface Item { code: string; path?: string }
interface Report {
  warnings: Item[];
  fixes: Item[];
  dictionaryProposals: { usedBy: unknown[] }[];
  extraction: { method: string };
  llm: { model: string };
  stats: unknown;
  timings: unknown;
  durationMs: number;
}

describe('mockConvertFile', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('resolves a reference form after delay', async () => {
    const out = run('a.pdf');
    await vi.advanceTimersByTimeAsync(1499);
    expect(out.value).toBeUndefined();
    await vi.advanceTimersByTimeAsync(3002);
    await vi.waitFor(() => expect(out.value).toBeDefined()); // dynamic import() resolves on real I/O
    const { form, report } = out.value as { form: { title: string; tabs: unknown[] }; report: Report };
    expect(form).toHaveProperty('title');
    expect(form).toHaveProperty('tabs');
    expect(report.durationMs).toBeGreaterThan(0);
  });

  it.each([0, 1])('report %i has paths that exist in its form', async (n) => {
    const outs = [run('a.pdf'), run('b.pdf')];
    await vi.advanceTimersByTimeAsync(5000);
    await vi.waitFor(() => expect(outs[n].value).toBeDefined());
    const { form, report } = outs[n].value as { form: unknown; report: Report };
    const exists = (path: string) =>
      path
        .match(/[^.[\]]+/g)!
        .reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], form) !== undefined;
    const draft = 'subject_pages[0].sections[0].fields[0]';
    expect(report.warnings.map((w) => w.path)).toContain(draft);
    expect(exists(draft)).toBe(false);
    const tabWarn = report.warnings.filter((w) => w.path?.startsWith('tabs['));
    expect(tabWarn.length).toBeGreaterThanOrEqual(1);
    expect(report.fixes.filter((f) => f.path?.startsWith('tabs[')).length).toBeGreaterThanOrEqual(1);
    for (const x of [...tabWarn, ...report.fixes.filter((f) => f.path)].filter((x) => x.path!.startsWith('tabs['))) {
      expect(exists(x.path!), x.path).toBe(true);
    }
    expect(report.dictionaryProposals).toHaveLength(1);
    expect(report.dictionaryProposals[0].usedBy.length).toBeGreaterThan(0);
    expect(report.extraction.method).toBe('pdf_text');
    expect(report.llm.model).toBeTruthy();
    expect(report.stats).toBeDefined();
    expect(report.timings).toBeDefined();
  });

  it('alternates reference forms', async () => {
    const a = run('a.pdf');
    const b = run('b.pdf');
    await vi.advanceTimersByTimeAsync(5000);
    await vi.waitFor(() => expect(a.value && b.value).toBeTruthy());
    expect((a.value as { form: { title: string } }).form.title).not.toBe((b.value as { form: { title: string } }).form.title);
  });

  it('fails with LLM_UNAVAILABLE for blad in name', async () => {
    const out = run('Formularz_BLAD.pdf');
    await vi.advanceTimersByTimeAsync(5000);
    const err = out.error as HttpErrorResponse;
    expect(err).toBeInstanceOf(HttpErrorResponse);
    expect(err.status).toBe(503);
    expect((err.error as { code: string }).code).toBe('LLM_UNAVAILABLE');
  });

  it.each([
    [undefined, 'DOCUMENT_PASSWORD_REQUIRED'],
    ['zle', 'DOCUMENT_PASSWORD_INVALID'],
  ])('asks for a password for haslo in name (password %s)', async (password, code) => {
    const out = run('umowa_haslo.pdf', password);
    await vi.advanceTimersByTimeAsync(5000);
    const err = out.error as HttpErrorResponse;
    expect(err.status).toBe(422);
    expect(err.error).toEqual({ code });
  });

  it('converts a haslo file with the demo password', async () => {
    const out = run('umowa_haslo.pdf', MOCK_DOCUMENT_PASSWORD);
    await vi.advanceTimersByTimeAsync(5000);
    await vi.waitFor(() => expect(out.value).toBeDefined());
  });
});
