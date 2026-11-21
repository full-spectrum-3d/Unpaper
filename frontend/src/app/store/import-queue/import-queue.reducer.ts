import { EntityState, createEntityAdapter } from '@ngrx/entity';
import { createReducer, on } from '@ngrx/store';
import { FileStatus } from '../../shared/ui/badge/badge';
import { ImportQueueActions } from './import-queue.actions';

export const importQueueFeatureKey = 'importQueue';

export interface QueueItem {
  id: string;
  name: string;
  size: number;
  status: FileStatus;
  error: string | null;
  /** false for client validation errors (retrying gives the same result), true for conversion errors */
  retryable: boolean;
  result: unknown | null;
  startedAt: number | null;
  durationMs: number | null;
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
  on(ImportQueueActions.convertSucceeded, (state, { id, result, durationMs }) =>
    state.entities[id]?.status !== 'processing'
      ? state
      : adapter.updateOne({ id, changes: { status: 'done', result, durationMs, error: null } }, state),
  ),
  on(ImportQueueActions.convertFailed, (state, { id, error }) =>
    state.entities[id]?.status !== 'processing'
      ? state
      : adapter.updateOne({ id, changes: { status: 'error', error, retryable: true } }, state),
  ),
  on(ImportQueueActions.retry, (state, { id }) => {
    const item = state.entities[id];
    if (item?.status !== 'error' || !item.retryable) return state;
    return adapter.updateOne({ id, changes: { status: 'pending', error: null } }, state);
  }),
  on(ImportQueueActions.removed, (state, { id }) =>
    state.entities[id]?.status === 'processing' ? state : adapter.removeOne(id, state),
  ),
);
