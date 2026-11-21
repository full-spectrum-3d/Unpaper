import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Store } from '@ngrx/store';
import { catchError, throwError } from 'rxjs';
import { selectToken } from '../store/auth/auth.selectors';
import { AuthActions } from '../store/auth/auth.actions';
import { TOKEN_URL } from './api-error';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const store = inject(Store);
  const token = store.selectSignal(selectToken);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && req.url !== TOKEN_URL) {
        // Only the first 401 logs out; the cleared token makes later ones no-ops.
        if (token() === null) return throwError(() => error);
        store.dispatch(AuthActions.logout({ reason: 'unauthorized' }));
      }
      return throwError(() => error);
    }),
  );
};
