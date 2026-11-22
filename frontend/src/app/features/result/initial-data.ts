import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';
import { InitialDataSource } from '../../shared/api/models/initial-data-source';
import { CatalogService } from '../../shared/api/services/catalog.service';

/**
 * Initial data sources with their attributes (`GET /initial-data-sources`), loaded once.
 * Without HttpClient (isolated tests, stories) or on error the list is empty: fields can still get a fixed default.
 */
@Injectable({ providedIn: 'root' })
export class InitialDataCatalog {
  readonly sources = toSignal(
    inject(HttpClient, { optional: true })
      ? inject(CatalogService)
          .listInitialDataSourcesApiV1InitialDataSourcesGet()
          .pipe(catchError(() => of([])))
      : of([]),
    { initialValue: [] as InitialDataSource[] },
  );
}
