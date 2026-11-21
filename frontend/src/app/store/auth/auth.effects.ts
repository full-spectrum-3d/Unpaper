import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Actions, createEffect, ofType, ROOT_EFFECTS_INIT } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { catchError, filter, map, merge, of, switchMap, tap, timer } from 'rxjs';
import { Router } from '@angular/router';
import { toUserMessage } from '../../core/api-error';
import { safeReturnUrl } from '../../core/auth.guard';
import { AuthService } from '../../shared/api/services/auth.service';
import { AuthActions } from './auth.actions';
import { selectExpiresAt, selectToken } from './auth.selectors';

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
        this.api.issueTokenApiV1AuthTokenPost({ body: { username, password } }).pipe(
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
                error: e instanceof HttpErrorResponse ? toUserMessage(e) : 'Wystąpił nieoczekiwany błąd',
              }),
            ),
          ),
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
      switchMap((at) => (at === null ? [] : timer(Math.max(0, at - Date.now())))),
      map(() => AuthActions.logout({ reason: 'expired' })),
    ),
  );

  logout$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(AuthActions.logout),
        filter(() => !this.router.url.startsWith('/login')),
        tap(({ reason }) => {
          const url = reason === 'manual' ? '/login' : '/login?returnUrl=' + encodeURIComponent(this.router.url);
          void this.router.navigateByUrl(url);
        }),
      ),
    { dispatch: false },
  );
}
