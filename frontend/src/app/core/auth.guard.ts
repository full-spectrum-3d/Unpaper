import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Store } from '@ngrx/store';
import { selectExpiresAt, selectToken } from '../store/auth/auth.selectors';

export function safeReturnUrl(raw: string | null): string {
  // backslash and control chars: browsers normalise `/\` and `/<tab>/` to `//` (protocol-relative)
  const safe = !!raw && raw.startsWith('/') && !raw.startsWith('//') && !/[\\\u0000-\u001f]/.test(raw);
  return safe && !raw.startsWith('/login') ? raw : '/import';
}

function hasValidSession(store: Store): boolean {
  const token = store.selectSignal(selectToken)();
  const expiresAt = store.selectSignal(selectExpiresAt)();
  return !!token && expiresAt !== null && expiresAt > Date.now();
}

export const authGuard: CanActivateFn = (_route, state) => {
  if (hasValidSession(inject(Store))) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

export const guestGuard: CanActivateFn = () =>
  hasValidSession(inject(Store)) ? inject(Router).createUrlTree(['/import']) : true;
