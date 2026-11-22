import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { Router, TitleStrategy, provideRouter } from '@angular/router';
import { AppTitleStrategy } from './core/title-strategy';
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

  it('focuses the page h1 after an in-app navigation, not on the first load', async () => {
    @Component({ selector: 'app-page-a', template: '<h1 tabindex="-1">A</h1>' })
    class PageA {}
    @Component({ selector: 'app-page-b', template: '<h1 tabindex="-1">B</h1>' })
    class PageB {}
    TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter([
          { path: 'a', component: PageA, title: 'Strona A' },
          { path: 'b', component: PageB },
        ]),
        { provide: TitleStrategy, useClass: AppTitleStrategy },
        provideMockStore({ initialState: { [authFeatureKey]: initialAuthState } }),
      ],
    });
    const fixture = TestBed.createComponent(App);
    document.body.appendChild(fixture.nativeElement);
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/a');
    await fixture.whenStable();
    expect(document.activeElement?.tagName).not.toBe('H1');
    expect(TestBed.inject(Title).getTitle()).toBe('Strona A – Cyfryzacja formularzy');
    await router.navigateByUrl('/b');
    await fixture.whenStable();
    expect(document.activeElement?.tagName).toBe('H1');
    expect(document.activeElement?.textContent).toBe('B');
    expect(TestBed.inject(Title).getTitle()).toBe('Cyfryzacja formularzy');
    fixture.nativeElement.remove();
  });
});
