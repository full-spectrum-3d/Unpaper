import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Store } from '@ngrx/store';
import { selectExpiresAt, selectToken } from '../store/auth/auth.selectors';

export function safeReturnUrl(raw: string | null): string {
  return raw && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/import';
}

export const authGuard: CanActivateFn = (_route, state) => {
  const store = inject(Store);
  const token = store.selectSignal(selectToken)();
  const expiresAt = store.selectSignal(selectExpiresAt)();
  if (token && expiresAt !== null && expiresAt > Date.now()) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

export const guestGuard: CanActivateFn = () =>
  inject(Store).selectSignal(selectToken)() !== null ? inject(Router).createUrlTree(['/import']) : true;
