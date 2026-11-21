import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { provideMockActions } from '@ngrx/effects/testing';
import { ROOT_EFFECTS_INIT } from '@ngrx/effects';
import { Action } from '@ngrx/store';
import { MockStore, provideMockStore } from '@ngrx/store/testing';
import { Observable, of, Subject, throwError } from 'rxjs';
import { AuthService } from '../../shared/api/services/auth.service';
import { AuthActions } from './auth.actions';
import { AuthEffects } from './auth.effects';
import { authFeatureKey } from './auth.reducer';

const NOW = 1_000_000;

function setup(opts: { url?: string; auth?: object; login?: Observable<unknown> } = {}) {
  const actions$ = new Subject<Action>();
  const issueToken = vi.fn(() => opts.login ?? of({ access_token: 'tok', expires_in: 60 }));
  TestBed.configureTestingModule({
    providers: [
      AuthEffects,
      provideRouter([]),
      provideMockActions(() => actions$),
      provideMockStore({
        initialState: { [authFeatureKey]: opts.auth ?? { token: null, expiresAt: null } },
      }),
      { provide: AuthService, useValue: { issueTokenApiV1AuthTokenPost: issueToken } },
    ],
  });
  const router = TestBed.inject(Router);
  vi.spyOn(router, 'url', 'get').mockReturnValue(opts.url ?? '/import');
  const navigate = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  const effects = TestBed.inject(AuthEffects);
  const out: Action[] = [];
  effects.login$.subscribe((a) => out.push(a));
  effects.expiryTimer$.subscribe((a) => out.push(a));
  effects.loginSuccess$.subscribe();
  effects.logout$.subscribe();
  return { actions$, out, navigate, issueToken, store: TestBed.inject(MockStore) };
}

describe('AuthEffects', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });
  afterEach(() => vi.useRealTimers());

  it('login success maps to loginSuccess with expiresAt', () => {
    const { actions$, out, issueToken } = setup();
    actions$.next(AuthActions.login({ username: 'u', password: 'p' }));
    expect(issueToken).toHaveBeenCalledWith({ body: { username: 'u', password: 'p' } });
    expect(out).toContainEqual(AuthActions.loginSuccess({ token: 'tok', expiresAt: NOW + 60000, username: 'u' }));
  });

  it('login failure maps to loginFailure with user message', () => {
    const err = new HttpErrorResponse({ status: 401, error: { code: 'INVALID_CREDENTIALS', detail: 'x' } });
    const { actions$, out } = setup({ login: throwError(() => err) });
    actions$.next(AuthActions.login({ username: 'u', password: 'p' }));
    expect(out).toContainEqual(AuthActions.loginFailure({ error: 'Nieprawidłowy login lub hasło' }));
  });

  it('navigates to returnUrl after login', () => {
    const { actions$, navigate } = setup({ url: '/login?returnUrl=%2Fwynik%2F1' });
    actions$.next(AuthActions.loginSuccess({ token: 't', expiresAt: NOW + 5000, username: 'u' }));
    expect(navigate).toHaveBeenCalledWith('/wynik/1');
  });

  it('navigates to /import for external returnUrl', () => {
    const { actions$, navigate } = setup({ url: '/login?returnUrl=%2F%2Fevil.com' });
    actions$.next(AuthActions.loginSuccess({ token: 't', expiresAt: NOW + 5000, username: 'u' }));
    expect(navigate).toHaveBeenCalledWith('/import');
  });

  it('expiry timer dispatches logout expired and new login cancels the old timer', () => {
    const { actions$, out } = setup();
    actions$.next(AuthActions.loginSuccess({ token: 't', expiresAt: NOW + 1000, username: 'u' }));
    actions$.next(AuthActions.loginSuccess({ token: 't', expiresAt: NOW + 5000, username: 'u' }));
    vi.advanceTimersByTime(1000);
    expect(out).not.toContainEqual(AuthActions.logout({ reason: 'expired' }));
    vi.advanceTimersByTime(4000);
    expect(out).toContainEqual(AuthActions.logout({ reason: 'expired' }));
  });

  it('logout cancels the expiry timer', () => {
    const { actions$, out } = setup();
    actions$.next(AuthActions.loginSuccess({ token: 't', expiresAt: NOW + 1000, username: 'u' }));
    actions$.next(AuthActions.logout({ reason: 'manual' }));
    vi.advanceTimersByTime(2000);
    expect(out).not.toContainEqual(AuthActions.logout({ reason: 'expired' }));
  });

  it('restored session starts timer', () => {
    const { actions$, out } = setup({ auth: { token: 't', expiresAt: NOW + 1000 } });
    actions$.next({ type: ROOT_EFFECTS_INIT });
    vi.advanceTimersByTime(1000);
    expect(out).toContainEqual(AuthActions.logout({ reason: 'expired' }));
  });

  it('logout navigates to /login', () => {
    const { actions$, navigate } = setup();
    actions$.next(AuthActions.logout({ reason: 'manual' }));
    expect(navigate).toHaveBeenCalledWith('/login');
  });

  it('expired logout keeps returnUrl', () => {
    const { actions$, navigate } = setup({ url: '/wynik/1' });
    actions$.next(AuthActions.logout({ reason: 'expired' }));
    expect(navigate).toHaveBeenCalledWith('/login?returnUrl=%2Fwynik%2F1');
  });

  it('unauthorized after manual logout does nothing', () => {
    const { actions$, navigate } = setup({ url: '/login' });
    actions$.next(AuthActions.logout({ reason: 'unauthorized' }));
    expect(navigate).not.toHaveBeenCalled();
  });
});
