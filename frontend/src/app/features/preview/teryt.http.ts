import { HttpClient } from '@angular/common/http';
import { EnvironmentProviders, inject, provideEnvironmentInitializer } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { Dictionary, setTerytLoader } from './sample-dictionaries';

export const TERYT_URL = '/api/v1/dictionaries/teryt';

// GET /api/v1/dictionaries/teryt: full TERYT tree, fetched once on first use; authInterceptor adds the bearer token.
export const provideHttpTeryt = (): EnvironmentProviders =>
  provideEnvironmentInitializer(() => {
    const http = inject(HttpClient);
    setTerytLoader(() => firstValueFrom(http.get<Dictionary>(TERYT_URL)));
  });
