import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { QueueItem } from './import-queue.reducer';

export const ImportQueueActions = createActionGroup({
  source: 'Import Queue',
  events: {
    filesAdded: props<{ items: QueueItem[] }>(),
    convertStarted: props<{ id: string; startedAt: number }>(),
    convertSucceeded: props<{ id: string; result: unknown; durationMs: number }>(),
    convertFailed: props<{ id: string; error: string }>(),
    retry: props<{ id: string }>(),
    removed: props<{ id: string }>(),
    /** A different user signed in: drop the previous user's queue. */
    cleared: emptyProps(),
  },
});
