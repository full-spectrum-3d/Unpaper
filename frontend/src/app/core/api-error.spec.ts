import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { TOKEN_URL, errorCode, toUserMessage } from './api-error';

const err = (status: number, error: unknown, extra: Partial<{ url: string; headers: HttpHeaders }> = {}) =>
  new HttpErrorResponse({ status, error, ...extra });

describe('toUserMessage', () => {
  it.each([
    ['INVALID_CREDENTIALS', 'Nieprawidłowy login lub hasło'],
    ['NOT_AUTHENTICATED', 'Sesja wygasła, zaloguj się ponownie'],
    ['INVALID_TOKEN', 'Sesja wygasła, zaloguj się ponownie'],
    ['FORBIDDEN', 'Brak uprawnień'],
    ['VALIDATION_ERROR', 'Uzupełnij login i hasło'],
    ['LLM_UNAVAILABLE', 'Usługa analizy formularzy jest chwilowo niedostępna. Spróbuj ponownie.'],
    ['PROCESSING_TIMEOUT', 'Przetwarzanie trwało zbyt długo. Spróbuj ponownie.'],
    ['DOCUMENT_PASSWORD_REQUIRED', 'Dokument jest zabezpieczony hasłem. Podaj hasło, aby go przetworzyć.'],
    ['DOCUMENT_PASSWORD_INVALID', 'Hasło jest niepoprawne. Spróbuj ponownie.'],
  ])('maps %s', (code, message) => {
    expect(toUserMessage(err(400, { code, detail: 'x' }))).toBe(message);
  });

  it('maps status 0 to connection message', () => {
    expect(toUserMessage(err(0, null))).toBe('Brak połączenia z serwerem');
  });

  it('maps 404 on token endpoint', () => {
    expect(toUserMessage(err(404, null, { url: TOKEN_URL }))).toBe(
      'Logowanie hasłem jest wyłączone w tej konfiguracji',
    );
  });

  it('does not treat 404 on other endpoints as disabled login', () => {
    expect(toUserMessage(err(404, null, { url: '/api/v1/forms' }))).toBe('Wystąpił nieoczekiwany błąd');
  });

  it('maps SERVER_BUSY', () => {
    expect(toUserMessage(err(503, { code: 'SERVER_BUSY', detail: 'x' }))).toBe(
      'Serwer jest zajęty. Spróbuj ponownie za chwilę.',
    );
  });

  it('maps an HTML 413 from the proxy by status', () => {
    expect(toUserMessage(err(413, '<html>413</html>'))).toBe('Plik jest zbyt duży');
  });

  it('prefers detail for 429, falls back by status without it', () => {
    expect(toUserMessage(err(429, { code: 'TOO_MANY_REQUESTS', detail: 'Za minutę.' }))).toBe('Za minutę.');
    expect(toUserMessage(err(429, null))).toBe('Zbyt wiele żądań. Spróbuj ponownie za chwilę.');
  });

  it('falls back to detail', () => {
    expect(toUserMessage(err(500, { code: 'OTHER', detail: 'Coś poszło nie tak' }))).toBe('Coś poszło nie tak');
  });

  it('falls back to generic message with request id', () => {
    const headers = new HttpHeaders({ 'X-Request-ID': 'abc' });
    expect(toUserMessage(err(500, null, { headers }))).toBe('Wystąpił nieoczekiwany błąd (kod zgłoszenia: abc)');
  });

  it('falls back to generic message without request id', () => {
    expect(toUserMessage(err(500, 'oops'))).toBe('Wystąpił nieoczekiwany błąd');
  });
});

describe('errorCode', () => {
  it('reads code from an HTTP error body', () => {
    expect(errorCode(err(422, { code: 'DOCUMENT_PASSWORD_REQUIRED' }))).toBe('DOCUMENT_PASSWORD_REQUIRED');
  });

  it('returns null without a string code', () => {
    expect(errorCode(err(500, null))).toBeNull();
    expect(errorCode(err(500, { code: 1 }))).toBeNull();
    expect(errorCode(new Error('x'))).toBeNull();
  });
});
