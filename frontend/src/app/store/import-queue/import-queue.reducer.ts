import { EntityState, createEntityAdapter } from '@ngrx/entity';
import { createReducer, on } from '@ngrx/store';
import { FileStatus } from '../../shared/ui/badge/badge';
import { AuthActions } from '../auth/auth.actions';
import { ImportQueueActions } from './import-queue.actions';

export const importQueueFeatureKey = 'importQueue';

/** The document is password-protected: no password sent yet, or the sent one was wrong. */
export type PasswordState = 'required' | 'invalid';

export interface QueueItem {
  id: string;
  name: string;
  size: number;
  status: FileStatus;
  error: string | null;
  /** false for client validation errors (retrying gives the same result), true for conversion errors */
  retryable: boolean;
  result: unknown | null;
  /** Backend conversion report; null when absent. Never part of the downloaded files. */
  report: unknown | null;
  startedAt: number | null;
  durationMs: number | null;
  passwordState?: PasswordState | null;
}

export type ImportQueueState = EntityState<QueueItem>;

export const adapter = createEntityAdapter<QueueItem>({ sortComparer: false });

export const initialImportQueueState: ImportQueueState = adapter.getInitialState();

export const importQueueReducer = createReducer(
  initialImportQueueState,
  on(ImportQueueActions.filesAdded, (state, { items }) => adapter.addMany(items, state)),
  // Transitions are guarded so a duplicate/stale action can never re-enter or revive an item.
  on(ImportQueueActions.convertStarted, (state, { id, startedAt }) =>
    state.entities[id]?.status !== 'pending'
      ? state
      : adapter.updateOne({ id, changes: { status: 'processing', startedAt } }, state),
  ),
  on(ImportQueueActions.convertSucceeded, (state, { id, result, report, durationMs }) =>
    state.entities[id]?.status !== 'processing'
      ? state
      : adapter.updateOne({ id, changes: { status: 'done', result, report, durationMs, error: null } }, state),
  ),
  on(ImportQueueActions.convertFailed, (state, { id, error, passwordState }) =>
    state.entities[id]?.status !== 'processing'
      ? state
      : adapter.updateOne(
          { id, changes: { status: 'error', error, retryable: true, passwordState: passwordState ?? null } },
          state,
        ),
  ),
  on(ImportQueueActions.passwordSubmitted, (state, { id }) => {
    const item = state.entities[id];
    if (item?.status !== 'error' || !item.passwordState) return state;
    return adapter.updateOne({ id, changes: { status: 'pending', error: null, passwordState: null } }, state);
  }),
  on(ImportQueueActions.retry, (state, { id }) => {
    const item = state.entities[id];
    if (item?.status !== 'error' || !item.retryable) return state;
    return adapter.updateOne({ id, changes: { status: 'pending', error: null, passwordState: null } }, state);
  }),
  on(ImportQueueActions.removed, (state, { id }) =>
    state.entities[id]?.status === 'processing' ? state : adapter.removeOne(id, state),
  ),
  // Late results of in-flight conversions then hit the missing-id guards above and are no-ops.
  on(ImportQueueActions.cleared, (state) => adapter.removeAll(state)),
  on(AuthActions.logout, (state, { reason }) => (reason === 'manual' ? adapter.removeAll(state) : state)),
);
