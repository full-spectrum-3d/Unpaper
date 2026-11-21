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
};

export function toUserMessage(error: HttpErrorResponse): string {
  if (error.status === 0) return 'Brak połączenia z serwerem';
  if (error.status === 404 && error.url?.endsWith(TOKEN_URL)) {
    return 'Logowanie hasłem jest wyłączone w tej konfiguracji';
  }
  const body = error.error as { code?: unknown; detail?: unknown } | null;
  if (typeof body?.code === 'string' && MESSAGES[body.code]) return MESSAGES[body.code];
  if (typeof body?.detail === 'string' && body.detail) return body.detail;
  const requestId = error.headers?.get('X-Request-ID');
  return 'Wystąpił nieoczekiwany błąd' + (requestId ? ` (kod zgłoszenia: ${requestId})` : '');
}
