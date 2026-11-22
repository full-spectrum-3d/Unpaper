import { createReducer, on } from '@ngrx/store';
import { AuthActions } from './auth.actions';

export const authFeatureKey = 'auth';

export interface AuthState {
  token: string | null;
  expiresAt: number | null;
  username: string | null;
  status: 'idle' | 'pending' | 'error';
  error: string | null;
  sessionExpired: boolean;
}

export const initialAuthState: AuthState = {
  token: null,
  expiresAt: null,
  username: null,
  status: 'idle',
  error: null,
  sessionExpired: false,
};

export const authReducer = createReducer(
  initialAuthState,
  on(AuthActions.login, AuthActions.register, (state): AuthState => ({
    ...state,
    status: 'pending',
    error: null,
    sessionExpired: false,
  })),
  on(AuthActions.loginSuccess, (state, { token, expiresAt, username }): AuthState => ({
    ...state,
    token,
    expiresAt,
    username,
    status: 'idle',
    error: null,
    sessionExpired: false,
  })),
  on(AuthActions.loginFailure, (state, { error }): AuthState => ({
    ...state,
    status: 'error',
    error,
  })),
  // Idempotent: parallel 401s or a logout after logout must not change state.
  on(AuthActions.logout, (state, { reason }): AuthState =>
    state.token === null
      ? state
      : {
          ...state,
          token: null,
          expiresAt: null,
          username: null,
          status: 'idle',
          error: null,
          sessionExpired: reason !== 'manual',
        },
  ),
);
