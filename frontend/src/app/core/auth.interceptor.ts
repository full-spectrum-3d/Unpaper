import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Store } from '@ngrx/store';
import { selectToken } from '../store/auth/auth.selectors';
import { TOKEN_URL } from './api-error';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(Store).selectSignal(selectToken)();
  if (!token || !req.url.startsWith('/api/') || req.url === TOKEN_URL) return next(req);
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};
