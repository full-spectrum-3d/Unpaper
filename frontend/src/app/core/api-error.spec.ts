import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { TOKEN_URL, toUserMessage } from './api-error';

const err = (status: number, error: unknown, extra: Partial<{ url: string; headers: HttpHeaders }> = {}) =>
  new HttpErrorResponse({ status, error, ...extra });

describe('toUserMessage', () => {
  it.each([
    ['INVALID_CREDENTIALS', 'Nieprawidłowy login lub hasło'],
    ['NOT_AUTHENTICATED', 'Sesja wygasła, zaloguj się ponownie'],
    ['INVALID_TOKEN', 'Sesja wygasła, zaloguj się ponownie'],
    ['FORBIDDEN', 'Brak uprawnień'],
    ['VALIDATION_ERROR', 'Uzupełnij login i hasło'],
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
