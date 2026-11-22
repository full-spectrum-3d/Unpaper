import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, map, of, shareReplay } from 'rxjs';
import { PredefinedDictionary } from '../../shared/api/models/predefined-dictionary';
import { ProposedDictionary } from '../../shared/api/models/proposed-dictionary';
import { CatalogService } from '../../shared/api/services/catalog.service';
import { DictionaryRef } from './form-edit';

export interface SelectDictionary extends DictionaryRef {
  description: string;
}

/** Dictionary not yet in eUsługi: a list takes its items as own options (`dictionaryName` is for predefined only). */
export interface ProposedSelectDictionary {
  name: string;
  title: string;
  description: string;
  items: string[];
}

/** Value prefix of a proposed dictionary in an "Źródło opcji" select (names never contain ':'). */
export const PROPOSED_PREFIX = 'proposed:';

type CatalogEntry = PredefinedDictionary | ProposedDictionary;

/**
 * Dictionaries a list (SELECT) can take its options from, loaded once from `GET /dictionaries`:
 * predefined ones are referenced by name, proposed ones are copied in as own options.
 * Without HttpClient (isolated component tests, stories) or when the request fails the lists are
 * empty: the editor then offers own options only.
 */
@Injectable({ providedIn: 'root' })
export class SelectDictionaries {
  private readonly all$ = inject(HttpClient, { optional: true })
    ? inject(CatalogService)
        .listDictionariesApiV1DictionariesGet()
        .pipe(
          map((all) => all as CatalogEntry[]),
          catchError(() => of([] as CatalogEntry[])),
          shareReplay(1),
        )
    : of([] as CatalogEntry[]);

  readonly list = toSignal(
    this.all$.pipe(
      map((all) =>
        all
          .filter(
            (d): d is PredefinedDictionary =>
              d.status === 'PREDEFINED' && d.fieldTypes.includes('SELECT'),
          )
          .map((d) => ({ name: d.name, description: d.description })),
      ),
    ),
    { initialValue: [] as SelectDictionary[] },
  );

  readonly proposed = toSignal(
    this.all$.pipe(
      map((all) =>
        all
          .filter(
            (d): d is ProposedDictionary =>
              d.status === 'PROPOSED' && d.fieldTypes.includes('SELECT') && d.items.length > 0,
          )
          .map((d) => ({
            name: d.name,
            title: d.title,
            description: d.description,
            items: d.items.map((i) => i.name),
          })),
      ),
    ),
    { initialValue: [] as ProposedSelectDictionary[] },
  );
}
