import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Store } from '@ngrx/store';
import { provideMockStore } from '@ngrx/store/testing';
import { AuthActions } from '../store/auth/auth.actions';
import { authFeatureKey } from '../store/auth/auth.reducer';
import { TOKEN_URL } from './api-error';
import { authInterceptor } from './auth.interceptor';
import { errorInterceptor } from './error.interceptor';

function setup(token: string | null) {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptors([authInterceptor, errorInterceptor])),
      provideHttpClientTesting(),
      provideMockStore({ initialState: { [authFeatureKey]: { token } } }),
    ],
  });
  return {
    http: TestBed.inject(HttpClient),
    ctrl: TestBed.inject(HttpTestingController),
    dispatch: vi.spyOn(TestBed.inject(Store), 'dispatch'),
  };
}

describe('interceptors', () => {
  it('adds bearer to /api/ requests', () => {
    const { http, ctrl } = setup('t1');
    http.get('/api/v1/dictionaries').subscribe();
    expect(ctrl.expectOne('/api/v1/dictionaries').request.headers.get('Authorization')).toBe('Bearer t1');
  });

  it('no bearer for token endpoint', () => {
    const { http, ctrl } = setup('t1');
    http.post(TOKEN_URL, {}).subscribe();
    expect(ctrl.expectOne(TOKEN_URL).request.headers.has('Authorization')).toBe(false);
  });

  it('no bearer for other hosts', () => {
    const { http, ctrl } = setup('t1');
    http.get('https://example.com/api/x').subscribe();
    expect(ctrl.expectOne('https://example.com/api/x').request.headers.has('Authorization')).toBe(false);
  });

  it('no bearer without token', () => {
    const { http, ctrl } = setup(null);
    http.get('/api/v1/dictionaries').subscribe();
    expect(ctrl.expectOne('/api/v1/dictionaries').request.headers.has('Authorization')).toBe(false);
  });

  it('401 dispatches logout unauthorized', () => {
    const { http, ctrl, dispatch } = setup('t1');
    const onError = vi.fn();
    http.get('/api/v1/dictionaries').subscribe({ error: onError });
    ctrl.expectOne('/api/v1/dictionaries').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(dispatch).toHaveBeenCalledWith(AuthActions.logout({ reason: 'unauthorized' }));
    expect(onError).toHaveBeenCalled();
  });

  it('401 on token endpoint does not logout', () => {
    const { http, ctrl, dispatch } = setup('t1');
    const onError = vi.fn();
    http.post(TOKEN_URL, {}).subscribe({ error: onError });
    ctrl.expectOne(TOKEN_URL).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(dispatch).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalled();
  });
});
