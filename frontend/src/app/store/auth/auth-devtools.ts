import { Action } from '@ngrx/store';
import { ImportQueueActions } from '../import-queue/import-queue.actions';
import { ImportQueueState, importQueueFeatureKey } from '../import-queue/import-queue.reducer';
import { AuthActions } from './auth.actions';
import { AuthState, authFeatureKey } from './auth.reducer';

const MASK = '***';

// Keeps the password, the JWT and conversion results (PII) out of Redux DevTools.
export function authActionSanitizer(action: Action, _id: number): Action {
  switch (action.type) {
    case AuthActions.login.type:
      return { ...action, password: MASK } as Action;
    case AuthActions.loginSuccess.type:
      return { ...action, token: MASK } as Action;
    case ImportQueueActions.convertSucceeded.type:
      return { ...action, result: MASK, report: MASK } as Action;
    default:
      return action;
  }
}

export function authStateSanitizer(state: unknown, _index: number): unknown {
  const s = state as { [authFeatureKey]?: AuthState; [importQueueFeatureKey]?: ImportQueueState };
  const auth = s[authFeatureKey];
  const queue = s[importQueueFeatureKey];
  return {
    ...s,
    ...(auth && { [authFeatureKey]: { ...auth, token: auth.token && MASK } }),
    ...(queue && {
      [importQueueFeatureKey]: {
        ...queue,
        entities: Object.fromEntries(
          Object.entries(queue.entities).map(([id, item]) => [
            id,
            item && { ...item, result: item.result && MASK, report: item.report && MASK },
          ]),
        ),
      },
    }),
  };
}
