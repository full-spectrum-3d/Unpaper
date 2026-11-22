import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, map, of } from 'rxjs';
import { PredefinedDictionary } from '../../shared/api/models/predefined-dictionary';
import { CatalogService } from '../../shared/api/services/catalog.service';
import { DictionaryRef } from './form-edit';

export interface SelectDictionary extends DictionaryRef {
  description: string;
}

/**
 * Predefined dictionaries a list (SELECT) can take its options from, loaded once from `GET /dictionaries`.
 * Without HttpClient (isolated component tests, stories) or when the request fails the list is empty:
 * the editor then offers own options only.
 */
@Injectable({ providedIn: 'root' })
export class SelectDictionaries {
  readonly list = toSignal(
    inject(HttpClient, { optional: true })
      ? inject(CatalogService)
          .listDictionariesApiV1DictionariesGet()
          .pipe(
            map((all) =>
              all
                .filter(
                  (d): d is PredefinedDictionary =>
                    d.status === 'PREDEFINED' && d.fieldTypes.includes('SELECT'),
                )
                .map((d) => ({
                  name: d.name,
                  description: d.description,
                })),
            ),
            catchError(() => of([])),
          )
      : of([]),
    { initialValue: [] as SelectDictionary[] },
  );
}
