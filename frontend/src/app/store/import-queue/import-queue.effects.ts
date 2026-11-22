import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Actions, ROOT_EFFECTS_INIT, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import {
  EMPTY,
  asapScheduler,
  catchError,
  filter,
  from,
  map,
  mergeMap,
  observeOn,
  of,
  takeUntil,
  tap,
  withLatestFrom,
} from 'rxjs';
import { errorCode, toUserMessage } from '../../core/api-error';
import { BATCH_CONCURRENCY, CONVERT_FILE } from '../../features/import/convert-file';
import { FileRegistry } from '../../features/import/file-registry';
import { AuthActions } from '../auth/auth.actions';
import { selectToken, selectUsername } from '../auth/auth.selectors';
import { ImportQueueActions as A } from './import-queue.actions';
import { PasswordState } from './import-queue.reducer';
import { selectQueueItems } from './import-queue.selectors';

const PASSWORD_STATES: Record<string, PasswordState> = {
  DOCUMENT_PASSWORD_REQUIRED: 'required',
  DOCUMENT_PASSWORD_INVALID: 'invalid',
};

@Injectable()
export class ImportQueueEffects {
  private readonly actions$ = inject(Actions);
  private readonly store = inject(Store);
  private readonly registry = inject(FileRegistry);
  private readonly convert = inject(CONVERT_FILE);
  /** Username the queue belongs to; in memory only, seeded from the restored session after a reload. */
  private owner: string | null = null;
  /** The queue is being emptied: in-flight uploads are aborted instead of running to completion. */
  private readonly queueDropped$ = this.actions$.pipe(
    ofType(A.cleared, AuthActions.logout),
    filter((a) => a.type !== AuthActions.logout.type || a.reason === 'manual'),
  );

  schedule$ = createEffect(() =>
    this.actions$.pipe(
      ofType(
        A.filesAdded,
        A.convertSucceeded,
        A.convertFailed,
        A.retry,
        A.passwordSubmitted,
        A.removed,
        AuthActions.loginSuccess,
      ),
      // Decide only once the dispatch queue has drained: inside it the state still lacks
      // already-queued actions (e.g. a synchronous failure), which caused duplicate starts.
      observeOn(asapScheduler),
      withLatestFrom(this.store.select(selectQueueItems), this.store.select(selectToken)),
      // Without a token every start would just fail with 401: wait for loginSuccess instead.
      filter(([, , token]) => token !== null),
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

  session$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ROOT_EFFECTS_INIT, AuthActions.logout, AuthActions.loginSuccess),
      withLatestFrom(this.store.select(selectUsername)),
      mergeMap(([action, restoredUser]) => {
        if (action.type === ROOT_EFFECTS_INIT) {
          // Without this a session restored from sessionStorage has no owner and the next
          // user logging in on this tab would inherit the queue.
          this.owner = restoredUser;
          return EMPTY;
        }
        if (action.type === AuthActions.logout.type) {
          if ((action as ReturnType<typeof AuthActions.logout>).reason === 'manual') {
            this.owner = null;
            this.registry.clear(); // the reducer clears the queue itself
          }
          return EMPTY;
        }
        const { username } = action as ReturnType<typeof AuthActions.loginSuccess>;
        const otherUser = this.owner !== null && this.owner !== username;
        this.owner = username;
        if (!otherUser) return EMPTY;
        this.registry.clear();
        return of(A.cleared());
      }),
    ),
  );

  cleanup$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(A.removed),
        observeOn(asapScheduler),
        withLatestFrom(this.store.select(selectQueueItems)),
        // The reducer keeps a processing item: its file is still needed.
        filter(([{ id }, items]) => !items.some((i) => i.id === id)),
        tap(([{ id }]) => this.registry.delete(id)),
      ),
    { dispatch: false },
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
        return this.convert(file, this.registry.password(id)).pipe(
          tap(() => this.registry.delete(id)),
          map(({ form, report }) => A.convertSucceeded({ id, result: form, report, durationMs: Date.now() - startedAt })),
          catchError((e: unknown) => {
            const passwordState = PASSWORD_STATES[errorCode(e) ?? ''] ?? null;
            // A rejected password is never resent; the user types it again.
            if (passwordState) this.registry.deletePassword(id);
            return of(
              A.convertFailed({
                id,
                error: e instanceof HttpErrorResponse ? toUserMessage(e) : 'Wystąpił nieoczekiwany błąd',
                passwordState,
              }),
            );
          }),
          takeUntil(this.queueDropped$),
        );
      }),
    ),
  );
}
