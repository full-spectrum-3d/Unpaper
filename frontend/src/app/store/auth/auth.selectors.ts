import { createFeatureSelector, createSelector } from '@ngrx/store';
import { AuthState, authFeatureKey } from './auth.reducer';

export const selectAuth = createFeatureSelector<AuthState>(authFeatureKey);
export const selectToken = createSelector(selectAuth, (s) => s.token);
export const selectExpiresAt = createSelector(selectAuth, (s) => s.expiresAt);
export const selectUsername = createSelector(selectAuth, (s) => s.username);
export const selectIsAuthenticated = createSelector(selectToken, (token) => token !== null);
export const selectLoginStatus = createSelector(selectAuth, (s) => s.status);
export const selectLoginError = createSelector(selectAuth, (s) => s.error);
export const selectSessionExpired = createSelector(selectAuth, (s) => s.sessionExpired);
