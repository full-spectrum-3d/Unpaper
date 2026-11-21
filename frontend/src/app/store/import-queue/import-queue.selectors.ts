import { createFeatureSelector, createSelector } from '@ngrx/store';
import { ImportQueueState, adapter, importQueueFeatureKey } from './import-queue.reducer';

export const selectImportQueue = createFeatureSelector<ImportQueueState>(importQueueFeatureKey);

const { selectAll } = adapter.getSelectors();

export const selectQueueItems = createSelector(selectImportQueue, selectAll);
export const selectQueueItem = (id: string) =>
  createSelector(selectImportQueue, (s) => s.entities[id]);
export const selectDoneItems = createSelector(selectQueueItems, (items) =>
  items.filter((i) => i.status === 'done'),
);
export const selectQueueCounts = createSelector(selectQueueItems, (items) => {
  const count = (status: string) => items.filter((i) => i.status === status).length;
  return {
    total: items.length,
    done: count('done'),
    error: count('error'),
    processing: count('processing'),
    pending: count('pending'),
  };
});
export const selectProcessingCount = createSelector(selectQueueCounts, (c) => c.processing);
