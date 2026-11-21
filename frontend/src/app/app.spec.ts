import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { MockStore, provideMockStore } from '@ngrx/store/testing';
import { App } from './app';
import { AuthActions } from './store/auth/auth.actions';
import { authFeatureKey, initialAuthState } from './store/auth/auth.reducer';

function setup(auth: Partial<typeof initialAuthState>) {
  TestBed.configureTestingModule({
    imports: [App],
    providers: [
      provideRouter([]),
      provideMockStore({ initialState: { [authFeatureKey]: { ...initialAuthState, ...auth } } }),
    ],
  });
  const fixture = TestBed.createComponent(App);
  fixture.detectChanges();
  return { fixture, el: fixture.nativeElement as HTMLElement, store: TestBed.inject(MockStore) };
}

describe('App', () => {
  it('shows topbar with username when authenticated', () => {
    const { el } = setup({ token: 't', expiresAt: Date.now() + 1000, username: 'dev' });
    expect(el.textContent).toContain('dev');
    expect(el.querySelector('button')?.textContent).toContain('Wyloguj');
  });

  it('hides topbar when anonymous', () => {
    const { el } = setup({});
    expect(el.querySelector('app-topbar')).toBeNull();
  });

  it('Wyloguj dispatches logout manual', () => {
    const { el, store } = setup({ token: 't', expiresAt: Date.now() + 1000, username: 'dev' });
    const spy = vi.spyOn(store, 'dispatch');
    (el.querySelector('button') as HTMLButtonElement).click();
    expect(spy).toHaveBeenCalledWith(AuthActions.logout({ reason: 'manual' }));
  });
});
