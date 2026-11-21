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

describe('mockConvertFile', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('resolves a reference form after delay', async () => {
    const out = run('a.pdf');
    await vi.advanceTimersByTimeAsync(1499);
    expect(out.value).toBeUndefined();
    await vi.advanceTimersByTimeAsync(3002);
    await vi.waitFor(() => expect(out.value).toBeDefined()); // dynamic import() resolves on real I/O
    expect(out.value).toHaveProperty('title');
    expect(out.value).toHaveProperty('tabs');
  });

  it('alternates reference forms', async () => {
    const a = run('a.pdf');
    const b = run('b.pdf');
    await vi.advanceTimersByTimeAsync(5000);
    await vi.waitFor(() => expect(a.value && b.value).toBeTruthy());
    expect((a.value as { title: string }).title).not.toBe((b.value as { title: string }).title);
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
