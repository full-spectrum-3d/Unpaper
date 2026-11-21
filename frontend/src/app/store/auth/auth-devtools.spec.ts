import { AuthActions } from './auth.actions';
import { authActionSanitizer } from './auth-devtools';

describe('authActionSanitizer', () => {
  it('masks password', () => {
    const out = authActionSanitizer(AuthActions.login({ username: 'dev', password: 'x' }), 0);
    expect(out).toEqual({ ...AuthActions.login({ username: 'dev', password: '***' }) });
  });

  it('leaves other actions unchanged', () => {
    const action = AuthActions.logout({ reason: 'manual' });
    expect(authActionSanitizer(action, 0)).toBe(action);
  });
});
