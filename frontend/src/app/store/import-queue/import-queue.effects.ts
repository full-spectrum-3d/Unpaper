import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { asapScheduler, catchError, filter, from, map, mergeMap, observeOn, of, tap, withLatestFrom } from 'rxjs';
import { toUserMessage } from '../../core/api-error';
import { BATCH_CONCURRENCY, CONVERT_FILE } from '../../features/import/convert-file';
import { FileRegistry } from '../../features/import/file-registry';
import { ImportQueueActions as A } from './import-queue.actions';
import { selectQueueItems } from './import-queue.selectors';

@Injectable()
export class ImportQueueEffects {
  private readonly actions$ = inject(Actions);
  private readonly store = inject(Store);
  private readonly registry = inject(FileRegistry);
  private readonly convert = inject(CONVERT_FILE);

  schedule$ = createEffect(() =>
    this.actions$.pipe(
      ofType(A.filesAdded, A.convertSucceeded, A.convertFailed, A.retry, A.removed),
      // Decide only once the dispatch queue has drained: inside it the state still lacks
      // already-queued actions (e.g. a synchronous failure), which caused duplicate starts.
      observeOn(asapScheduler),
      withLatestFrom(this.store.select(selectQueueItems)),
      mergeMap(([, items]) => {
        const free = BATCH_CONCURRENCY - items.filter((i) => i.status === 'processing').length;
        return from(
          items
            .filter((i) => i.status === 'pending')
            .slice(0, Math.max(free, 0))
            .map((i) => A.convertStarted({ id: i.id, startedAt: Date.now() })),
        );
      }),
    ),
  );

  convert$ = createEffect(() =>
    this.actions$.pipe(
      ofType(A.convertStarted),
      withLatestFrom(this.store.select(selectQueueItems)),
      // Run only the start that actually moved the item to processing (reducer ignores duplicates).
      filter(([{ id, startedAt }, items]) => {
        const it = items.find((i) => i.id === id);
        return it?.status === 'processing' && it.startedAt === startedAt;
      }),
      mergeMap(([{ id, startedAt }]) => {
        const file = this.registry.get(id);
        if (!file) return of(A.convertFailed({ id, error: 'Plik niedostępny – dodaj go ponownie' }));
        return this.convert(file).pipe(
          tap(() => this.registry.delete(id)),
          map((result) => A.convertSucceeded({ id, result, durationMs: Date.now() - startedAt })),
          catchError((e: unknown) =>
            of(
              A.convertFailed({
                id,
                error: e instanceof HttpErrorResponse ? toUserMessage(e) : 'Wystąpił nieoczekiwany błąd',
              }),
            ),
          ),
        );
      }),
    ),
  );
}
