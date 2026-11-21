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
      const ownApi = req.url.startsWith('/api/') && req.url !== TOKEN_URL;
      if (error instanceof HttpErrorResponse && error.status === 401 && ownApi) {
        // Only the first 401 logs out; the cleared token makes later ones no-ops.
        if (token() === null) return throwError(() => error);
        store.dispatch(AuthActions.logout({ reason: 'unauthorized' }));
      }
      return throwError(() => error);
    }),
  );
};
