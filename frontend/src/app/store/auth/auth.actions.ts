import { createActionGroup, props } from '@ngrx/store';

export const AuthActions = createActionGroup({
  source: 'Auth',
  events: {
    login: props<{ username: string; password: string }>(),
    register: props<{ username: string; password: string }>(),
    loginSuccess: props<{ token: string; expiresAt: number; username: string }>(),
    loginFailure: props<{ error: string }>(),
    logout: props<{ reason: 'manual' | 'expired' | 'unauthorized' }>(),
  },
});
