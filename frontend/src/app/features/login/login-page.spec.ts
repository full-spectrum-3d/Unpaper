import { TestBed } from '@angular/core/testing';
import { MockStore, provideMockStore } from '@ngrx/store/testing';
import { AuthActions } from '../../store/auth/auth.actions';
import { AuthState, authFeatureKey, initialAuthState } from '../../store/auth/auth.reducer';
import { LoginPage } from './login-page';

async function setup(auth: Partial<AuthState> = {}) {
  TestBed.configureTestingModule({
    providers: [
      provideMockStore({ initialState: { [authFeatureKey]: { ...initialAuthState, ...auth } } }),
    ],
  });
  const fixture = TestBed.createComponent(LoginPage);
  document.body.appendChild(fixture.nativeElement);
  await fixture.whenStable();
  const el: HTMLElement = fixture.nativeElement;
  const store = TestBed.inject(MockStore);
  const dispatch = vi.spyOn(store, 'dispatch');
  const inputs = () => [...el.querySelectorAll('input')];
  const type = (input: HTMLInputElement, value: string) => {
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };
  const submit = async () => {
    el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await fixture.whenStable();
  };
  return { fixture, el, store, dispatch, inputs, type, submit };
}

describe('LoginPage', () => {
  afterEach(() => (document.body.innerHTML = ''));

  it('marks both fields as required', async () => {
    const { inputs } = await setup();
    expect(inputs().map((i) => i.getAttribute('aria-required'))).toEqual(['true', 'true']);
  });

  it('shows errors and focuses the first invalid field without dispatching', async () => {
    const { el, dispatch, inputs, type, submit } = await setup();
    type(inputs()[0], 'dev');
    await submit();
    expect(dispatch).not.toHaveBeenCalled();
    expect(el.textContent).toContain('Pole wymagane');
    expect(document.activeElement).toBe(inputs()[1]);
    expect(inputs()[1].getAttribute('aria-invalid')).toBe('true');
  });

  it('dispatches login with the typed credentials', async () => {
    const { dispatch, inputs, type, submit } = await setup();
    type(inputs()[0], 'dev');
    type(inputs()[1], 'tajne');
    await submit();
    expect(dispatch).toHaveBeenCalledWith(
      AuthActions.login({ username: 'dev', password: 'tajne' }),
    );
  });

  it('focuses the login error alert', async () => {
    const { el } = await setup({ status: 'error', error: 'Nieprawidłowy login lub hasło' });
    const alert = el.querySelector('[role="alert"]')!;
    expect(alert.textContent).toContain('Nieprawidłowy login lub hasło');
    expect(document.activeElement).toBe(alert);
  });

  it('fills the persistent status region after render when the session expired', async () => {
    const { el } = await setup({ sessionExpired: true });
    const status = el.querySelector('[role="status"]')!;
    expect(status.textContent!.trim()).toBe('Sesja wygasła, zaloguj się ponownie');
  });

  it('keeps an empty status region otherwise', async () => {
    const { el } = await setup();
    expect(el.querySelector('[role="status"]')!.textContent!.trim()).toBe('');
  });
});
