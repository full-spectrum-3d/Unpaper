import { ApplicationConfig, provideBrowserGlobalErrorListeners, isDevMode } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';
import { provideApiConfiguration } from './shared/api/api-configuration';
import { provideStore } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { provideStoreDevtools } from '@ngrx/store-devtools';
import { authInterceptor } from './core/auth.interceptor';
import { errorInterceptor } from './core/error.interceptor';
import { authActionSanitizer } from './store/auth/auth-devtools';
import { AuthEffects } from './store/auth/auth.effects';
import { authReducer, authFeatureKey } from './store/auth/auth.reducer';
import { authStorageMetaReducer } from './store/auth/auth.storage';
import { provideMockConvertFile } from './features/import/convert-file.mock';
import { ImportQueueEffects } from './store/import-queue/import-queue.effects';
import { importQueueFeatureKey, importQueueReducer } from './store/import-queue/import-queue.reducer';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([authInterceptor, errorInterceptor])),
    provideApiConfiguration(''),
    // meta-reducer wraps the slice reducer: restore relies on @ngrx/store/init
    provideStore({
      [authFeatureKey]: authStorageMetaReducer(authReducer),
      [importQueueFeatureKey]: importQueueReducer,
    }),
    provideEffects(AuthEffects, ImportQueueEffects),
    provideMockConvertFile(),
    provideStoreDevtools({
      maxAge: 25,
      logOnly: !isDevMode(),
      actionSanitizer: authActionSanitizer,
    }),
  ],
};
