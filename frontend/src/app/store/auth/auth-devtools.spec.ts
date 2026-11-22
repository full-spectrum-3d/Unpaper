import { AuthActions } from './auth.actions';
import { ImportQueueActions } from '../import-queue/import-queue.actions';
import { authActionSanitizer, authStateSanitizer } from './auth-devtools';

describe('authActionSanitizer', () => {
  it('masks the password of a new account', () => {
    const out = authActionSanitizer(AuthActions.register({ username: 'dev', password: 'x' }), 0);
    expect(out).toEqual({ ...AuthActions.register({ username: 'dev', password: '***' }) });
  });

  it('masks password', () => {
    const out = authActionSanitizer(AuthActions.login({ username: 'dev', password: 'x' }), 0);
    expect(out).toEqual({ ...AuthActions.login({ username: 'dev', password: '***' }) });
  });

  it('leaves other actions unchanged', () => {
    const action = AuthActions.logout({ reason: 'manual' });
    expect(authActionSanitizer(action, 0)).toBe(action);
  });
});

describe('authStateSanitizer', () => {
  it('masks token and queue results, keeps the rest', () => {
    const item = {
      id: 'a',
      name: 'x.pdf',
      result: { pesel: '1' },
      report: { r: 1 },
      status: 'done',
    };
    const out = authStateSanitizer(
      {
        auth: { token: 'jwt', username: 'dev' },
        importQueue: { ids: ['a'], entities: { a: item } },
        other: 1,
      },
      0,
    );
    expect(out).toEqual({
      auth: { token: '***', username: 'dev' },
      importQueue: { ids: ['a'], entities: { a: { ...item, result: '***', report: '***' } } },
      other: 1,
    });
  });

  it('leaves null token and missing slices alone', () => {
    expect(authStateSanitizer({ auth: { token: null } }, 0)).toEqual({ auth: { token: null } });
  });
});

describe('authActionSanitizer secrets', () => {
  it('masks the token and conversion results', () => {
    expect(
      authActionSanitizer(AuthActions.loginSuccess({ token: 't', expiresAt: 1, username: 'u' }), 0),
    ).toMatchObject({
      token: '***',
    });
    expect(
      authActionSanitizer(
        ImportQueueActions.convertSucceeded({ id: 'a', result: {}, report: null, durationMs: 1 }),
        0,
      ),
    ).toMatchObject({ result: '***', report: '***' });
    expect(
      authActionSanitizer(ImportQueueActions.resultEdited({ id: 'a', result: {} }), 0),
    ).toMatchObject({ result: '***' });
  });
});
