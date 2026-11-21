import { AuthActions } from './auth.actions';
import { AuthState, authReducer, initialAuthState } from './auth.reducer';

const loggedIn: AuthState = { ...initialAuthState, token: 't', expiresAt: 10, username: 'u' };

describe('authReducer', () => {
  it('login sets pending and clears error and sessionExpired', () => {
    const before = { ...initialAuthState, error: 'x', sessionExpired: true };
    const state = authReducer(before, AuthActions.login({ username: 'u', password: 's3cret-pw' }));
    expect(state.status).toBe('pending');
    expect(state.error).toBeNull();
    expect(state.sessionExpired).toBe(false);
    expect(JSON.stringify(state)).not.toContain('s3cret-pw');
  });

  it('loginSuccess stores token, expiresAt, username and idles', () => {
    const state = authReducer(
      { ...initialAuthState, status: 'pending', sessionExpired: true },
      AuthActions.loginSuccess({ token: 't', expiresAt: 99, username: 'u' }),
    );
    expect(state).toEqual({
      token: 't',
      expiresAt: 99,
      username: 'u',
      status: 'idle',
      error: null,
      sessionExpired: false,
    });
  });

  it('loginFailure sets error status and message', () => {
    const state = authReducer(initialAuthState, AuthActions.loginFailure({ error: 'zle' }));
    expect(state.status).toBe('error');
    expect(state.error).toBe('zle');
  });

  it('logout clears token; expired/unauthorized set sessionExpired, manual does not', () => {
    for (const [reason, expired] of [
      ['manual', false],
      ['expired', true],
      ['unauthorized', true],
    ] as const) {
      const state = authReducer(loggedIn, AuthActions.logout({ reason }));
      expect(state.token).toBeNull();
      expect(state.expiresAt).toBeNull();
      expect(state.username).toBeNull();
      expect(state.sessionExpired).toBe(expired);
    }
  });

  it('logout is idempotent', () => {
    const state = authReducer(initialAuthState, AuthActions.logout({ reason: 'unauthorized' }));
    expect(state).toBe(initialAuthState);
  });
});
