import { HttpErrorResponse } from '@angular/common/http';

export const TOKEN_URL = '/api/v1/auth/token';

const MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: 'Nieprawidłowy login lub hasło',
  NOT_AUTHENTICATED: 'Sesja wygasła, zaloguj się ponownie',
  INVALID_TOKEN: 'Sesja wygasła, zaloguj się ponownie',
  FORBIDDEN: 'Brak uprawnień',
  VALIDATION_ERROR: 'Uzupełnij login i hasło',
  LLM_UNAVAILABLE: 'Usługa analizy formularzy jest chwilowo niedostępna. Spróbuj ponownie.',
  PROCESSING_TIMEOUT: 'Przetwarzanie trwało zbyt długo. Spróbuj ponownie.',
  DOCUMENT_PASSWORD_REQUIRED:
    'Dokument jest zabezpieczony hasłem. Podaj hasło, aby go przetworzyć.',
  DOCUMENT_PASSWORD_INVALID: 'Hasło jest niepoprawne. Spróbuj ponownie.',
};

/** Machine-readable `code` from a problem+json error body, if any. */
export function errorCode(error: unknown): string | null {
  const body =
    error instanceof HttpErrorResponse ? (error.error as { code?: unknown } | null) : null;
  return typeof body?.code === 'string' ? body.code : null;
}

export function toUserMessage(error: HttpErrorResponse): string {
  if (error.status === 0) return 'Brak połączenia z serwerem';
  if (error.status === 404 && error.url?.endsWith(TOKEN_URL)) {
    return 'Logowanie hasłem jest wyłączone w tej konfiguracji';
  }
  const code = errorCode(error);
  if (code && MESSAGES[code]) return MESSAGES[code];
  const detail = (error.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return detail;
  const requestId = error.headers?.get('X-Request-ID');
  return 'Wystąpił nieoczekiwany błąd' + (requestId ? ` (kod zgłoszenia: ${requestId})` : '');
}
