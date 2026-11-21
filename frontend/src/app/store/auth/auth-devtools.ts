import { Action } from '@ngrx/store';
import { AuthActions } from './auth.actions';

// Keeps the password out of Redux DevTools.
export function authActionSanitizer(action: Action, _id: number): Action {
  return action.type === AuthActions.login.type ? { ...action, password: '***' } as Action : action;
}
