import { TestBed } from '@angular/core/testing';
import { provideStore, Store } from '@ngrx/store';
import { authFeatureKey, authReducer } from './auth.reducer';
import { selectToken } from './auth.selectors';
import { AUTH_STORAGE_KEY, authStorageMetaReducer } from './auth.storage';

describe('auth root wiring', () => {
  afterEach(() => sessionStorage.clear());

  it('restores the stored session into the store', () => {
    sessionStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({ token: 't', expiresAt: Date.now() + 60_000, username: 'u' }),
    );
    TestBed.configureTestingModule({
      providers: [provideStore({ [authFeatureKey]: authStorageMetaReducer(authReducer) })],
    });
    expect(TestBed.inject(Store).selectSignal(selectToken)()).toBe('t');
  });
});
