import { HttpErrorResponse } from '@angular/common/http';
import { Provider } from '@angular/core';
import { defer, from, switchMap, throwError, timer } from 'rxjs';
import { CONVERT_FILE, ConvertFileFn } from './convert-file';

// Lazy chunks: reference forms stay out of the initial bundle.
const FORMS = [
  () => import('./mock-forms/nadplata-podatku.json'),
  () => import('./mock-forms/numer-porzadkowy.json'),
];
let next = 0;

/** Demo password for files with "haslo" in the name. */
export const MOCK_DOCUMENT_PASSWORD = 'test';

const fail = (status: number, code: string) =>
  throwError(() => new HttpErrorResponse({ status, error: { code } }));

export const mockConvertFile: ConvertFileFn = (file, password) =>
  defer(() => {
    const load = FORMS[next++ % FORMS.length];
    return timer(1500 + Math.random() * 2500).pipe(
      switchMap(() => {
        if (/blad/i.test(file.name)) return fail(503, 'LLM_UNAVAILABLE');
        if (/haslo/i.test(file.name) && password !== MOCK_DOCUMENT_PASSWORD) {
          return fail(422, password ? 'DOCUMENT_PASSWORD_INVALID' : 'DOCUMENT_PASSWORD_REQUIRED');
        }
        return from(load().then((m) => m.default));
      }),
    );
  });

export const provideMockConvertFile = (): Provider => ({
  provide: CONVERT_FILE,
  useValue: mockConvertFile,
});
