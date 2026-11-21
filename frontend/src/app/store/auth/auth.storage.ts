import { ActionReducer } from '@ngrx/store';
import { AuthState } from './auth.reducer';

export const AUTH_STORAGE_KEY = 'coi-cf.auth';

interface StoredSession {
  token: string;
  expiresAt: number;
  username: string | null;
}

function read(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (raw === null) return null;
    const v = JSON.parse(raw);
    const valid =
      typeof v?.token === 'string' &&
      typeof v.expiresAt === 'number' &&
      (typeof v.username === 'string' || v.username === null) &&
      v.expiresAt > Date.now();
    return valid ? { token: v.token, expiresAt: v.expiresAt, username: v.username } : null;
  } catch {
    return null;
  }
}

function write(state: AuthState): void {
  try {
    if (state.token === null) {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
    } else {
      const session: StoredSession = {
        token: state.token,
        expiresAt: state.expiresAt as number,
        username: state.username,
      };
      sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    }
  } catch {
    // Storage unavailable: the session just won't survive a reload.
  }
}

/** Meta-reducer over the auth slice state (use with a reducer for AuthState only). */
export function authStorageMetaReducer<A extends { type: string }>(
  reducer: ActionReducer<AuthState, A>,
): ActionReducer<AuthState, A> {
  return (state, action) => {
    let current = state;
    if (action.type === '@ngrx/store/init') {
      const saved = read();
      if (saved) current = { ...reducer(undefined, action), ...saved };
    }
    const next = reducer(current, action);
    write(next);
    return next;
  };
}
