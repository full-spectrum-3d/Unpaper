import { createActionGroup, emptyProps, props } from '@ngrx/store';
import { PasswordState, QueueItem } from './import-queue.reducer';

export const ImportQueueActions = createActionGroup({
  source: 'Import Queue',
  events: {
    filesAdded: props<{ items: QueueItem[] }>(),
    convertStarted: props<{ id: string; startedAt: number }>(),
    convertSucceeded: props<{ id: string; result: unknown; report: unknown | null; durationMs: number }>(),
    convertFailed: props<{ id: string; error: string; passwordState?: PasswordState | null }>(),
    /** The password itself lives in FileRegistry, never in the store. */
    passwordSubmitted: props<{ id: string }>(),
    retry: props<{ id: string }>(),
    removed: props<{ id: string }>(),
    /** A different user signed in: drop the previous user's queue. */
    cleared: emptyProps(),
  },
});
