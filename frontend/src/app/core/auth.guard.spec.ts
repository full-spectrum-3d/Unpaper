import { TestBed } from '@angular/core/testing';
import { CanActivateFn, provideRouter, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { provideMockStore } from '@ngrx/store/testing';
import { authFeatureKey } from '../store/auth/auth.reducer';
import { authGuard, guestGuard, safeReturnUrl } from './auth.guard';

const NOW = 1_000_000;

function run(guard: CanActivateFn, auth: { token: string | null; expiresAt: number | null }, url = '/wynik/1?a=b') {
  TestBed.configureTestingModule({
    providers: [provideRouter([]), provideMockStore({ initialState: { [authFeatureKey]: auth } })],
  });
  return TestBed.runInInjectionContext(() => guard({} as never, { url } as RouterStateSnapshot));
}

const asUrl = (r: unknown) => TestBed.inject(Router).serializeUrl(r as UrlTree);

describe('guards', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });
  afterEach(() => vi.useRealTimers());

  it('authGuard allows valid token', () => {
    expect(run(authGuard, { token: 't', expiresAt: NOW + 1 })).toBe(true);
  });

  it('guard rejects expired token', () => {
    const r = run(authGuard, { token: 't', expiresAt: NOW - 1 });
    expect(asUrl(r)).toBe('/login?returnUrl=%2Fwynik%2F1%3Fa%3Db');
  });

  it('authGuard redirects without token with returnUrl', () => {
    const r = run(authGuard, { token: null, expiresAt: null }, '/import');
    expect(asUrl(r)).toBe('/login?returnUrl=%2Fimport');
  });

  it('guestGuard sends authenticated user to /import', () => {
    expect(asUrl(run(guestGuard, { token: 't', expiresAt: NOW + 1 }))).toBe('/import');
  });

  it('guestGuard allows login when token is expired', () => {
    expect(run(guestGuard, { token: 't', expiresAt: NOW - 1 })).toBe(true);
  });

  it('guestGuard allows anonymous', () => {
    expect(run(guestGuard, { token: null, expiresAt: null })).toBe(true);
  });
});

describe('safeReturnUrl', () => {
  it.each([
    ['//evil.com', '/import'],
    ['https://evil.com', '/import'],
    [null, '/import'],
    ['/wynik/1', '/wynik/1'],
    ['/\\evil.com', '/import'],
    ['/\\/evil.com', '/import'],
    ['/\t/evil.com', '/import'],
    ['/a\nb', '/import'],
    ['/%2F%2Fevil.com', '/%2F%2Fevil.com'],
    ['', '/import'],
    ['/login', '/import'],
    ['/login?returnUrl=%2Fx', '/import'],
  ])('%s -> %s', (raw, expected) => {
    expect(safeReturnUrl(raw)).toBe(expected);
  });
});
