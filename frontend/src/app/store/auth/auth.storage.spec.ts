import { Action } from '@ngrx/store';
import { AuthActions } from './auth.actions';
import { AuthState, authReducer, initialAuthState } from './auth.reducer';
import { AUTH_STORAGE_KEY, authStorageMetaReducer } from './auth.storage';

const INIT = { type: '@ngrx/store/init' };
const reducer = authStorageMetaReducer((state: AuthState | undefined, action: Action) =>
  authReducer(state, action as never),
);

describe('authStorageMetaReducer', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it('persists token after loginSuccess', () => {
    reducer(
      initialAuthState,
      AuthActions.loginSuccess({ token: 't', expiresAt: 99, username: 'u' }),
    );
    const stored = JSON.parse(sessionStorage.getItem(AUTH_STORAGE_KEY)!);
    expect(stored).toEqual({ token: 't', expiresAt: 99, username: 'u' });
    expect(stored).not.toHaveProperty('password');
  });

  it('does not write storage for actions that leave the session unchanged', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem');
    const state = { ...initialAuthState, token: 't', expiresAt: 99, username: 'u' };
    reducer(state, { type: 'other' });
    reducer(state, AuthActions.loginFailure({ error: 'x' }));
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();
  });

  it('removes entry on logout', () => {
    sessionStorage.setItem(AUTH_STORAGE_KEY, '{}');
    reducer(
      { ...initialAuthState, token: 't', expiresAt: 99, username: 'u' },
      AuthActions.logout({ reason: 'manual' }),
    );
    expect(sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it('restores valid entry on init', () => {
    const expiresAt = Date.now() + 60_000;
    sessionStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({ token: 't', expiresAt, username: 'u' }),
    );
    expect(reducer(undefined, INIT)).toEqual({
      ...initialAuthState,
      token: 't',
      expiresAt,
      username: 'u',
    });
  });

  it('drops expired entry on init', () => {
    sessionStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({ token: 't', expiresAt: Date.now() - 1, username: 'u' }),
    );
    expect(reducer(undefined, INIT)).toEqual(initialAuthState);
  });

  it('ignores corrupted storage entry', () => {
    for (const raw of ['{', '{"token":1}']) {
      sessionStorage.setItem(AUTH_STORAGE_KEY, raw);
      expect(reducer(undefined, INIT)).toEqual(initialAuthState);
    }
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(reducer(undefined, INIT)).toEqual(initialAuthState);
  });
});
