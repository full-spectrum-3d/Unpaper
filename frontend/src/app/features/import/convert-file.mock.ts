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

export const mockConvertFile: ConvertFileFn = (file) =>
  defer(() => {
    const load = FORMS[next++ % FORMS.length];
    return timer(1500 + Math.random() * 2500).pipe(
      switchMap(() =>
        /blad/i.test(file.name)
          ? throwError(
              () => new HttpErrorResponse({ status: 503, error: { code: 'LLM_UNAVAILABLE' } }),
            )
          : from(load().then((m) => m.default)),
      ),
    );
  });

export const provideMockConvertFile = (): Provider => ({
  provide: CONVERT_FILE,
  useValue: mockConvertFile,
});
