import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Actions, createEffect, ofType, ROOT_EFFECTS_INIT } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { Observable, catchError, defer, filter, map, merge, of, switchMap, tap, timer } from 'rxjs';
import { Router } from '@angular/router';
import { toUserMessage } from '../../core/api-error';
import { safeReturnUrl } from '../../core/auth.guard';
import { TokenResponse } from '../../shared/api/models/token-response';
import { AuthService } from '../../shared/api/services/auth.service';
import { AuthActions } from './auth.actions';
import { selectExpiresAt, selectToken } from './auth.selectors';

/** setTimeout fires at once for delays above 2^31-1 ms (~24.8 days). */
const MAX_TIMER_MS = 2 ** 31 - 1;

/** Emits once at the epoch time `at`, re-arming in steps when it is further away than the timer limit. */
export function timerUntil(at: number): Observable<unknown> {
  return defer(() => {
    const delay = at - Date.now();
    return delay > MAX_TIMER_MS
      ? timer(MAX_TIMER_MS).pipe(switchMap(() => timerUntil(at)))
      : timer(Math.max(0, delay));
  });
}

@Injectable()
export class AuthEffects {
  private readonly actions$ = inject(Actions);
  private readonly store = inject(Store);
  private readonly router = inject(Router);
  private readonly api = inject(AuthService);

  login$ = createEffect(() =>
    this.actions$.pipe(
      ofType(AuthActions.login),
      switchMap(({ username, password }) =>
        this.signIn(
          username,
          this.api.issueTokenApiV1AuthTokenPost({ body: { username, password } }),
        ),
      ),
    ),
  );

  /** A new account is signed in straight away: the API answers registration with a token. */
  register$ = createEffect(() =>
    this.actions$.pipe(
      ofType(AuthActions.register),
      switchMap(({ username, password }) =>
        this.signIn(
          username,
          this.api.registerApiV1AuthRegisterPost({ body: { username, password } }),
        ),
      ),
    ),
  );

  loginSuccess$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(AuthActions.loginSuccess),
        tap(() => {
          const raw = this.router.parseUrl(this.router.url).queryParams['returnUrl'] ?? null;
          void this.router.navigateByUrl(safeReturnUrl(raw));
        }),
      ),
    { dispatch: false },
  );

  expiryTimer$ = createEffect(() =>
    merge(
      this.actions$.pipe(
        ofType(AuthActions.loginSuccess),
        map((a) => a.expiresAt),
      ),
      this.actions$.pipe(
        ofType(ROOT_EFFECTS_INIT),
        map(() => ({
          token: this.store.selectSignal(selectToken)(),
          expiresAt: this.store.selectSignal(selectExpiresAt)(),
        })),
        filter((s) => s.token !== null && s.expiresAt !== null),
        map((s) => s.expiresAt as number),
      ),
      this.actions$.pipe(
        ofType(AuthActions.logout),
        map(() => null),
      ),
    ).pipe(
      switchMap((at) => (at === null ? [] : timerUntil(at))),
      map(() => AuthActions.logout({ reason: 'expired' })),
    ),
  );

  logout$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(AuthActions.logout),
        filter(() => !this.router.url.startsWith('/login')),
        tap(({ reason }) => {
          const url =
            reason === 'manual'
              ? '/login'
              : '/login?returnUrl=' + encodeURIComponent(this.router.url);
          void this.router.navigateByUrl(url);
        }),
      ),
    { dispatch: false },
  );

  private signIn(username: string, request: Observable<TokenResponse>) {
    return request.pipe(
      map((r) =>
        AuthActions.loginSuccess({
          token: r.access_token,
          expiresAt: Date.now() + r.expires_in * 1000,
          username,
        }),
      ),
      catchError((e: unknown) =>
        of(
          AuthActions.loginFailure({
            error:
              e instanceof HttpErrorResponse ? toUserMessage(e) : 'Wystąpił nieoczekiwany błąd',
          }),
        ),
      ),
    );
  }
}
