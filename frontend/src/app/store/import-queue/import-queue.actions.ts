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
    /** The user stopped a conversion in progress; the file stays so it can be retried. */
    cancelled: props<{ id: string }>(),
    retry: props<{ id: string }>(),
    /** The user edited the converted form on the result screen; the report stays the original one. */
    resultEdited: props<{ id: string; result: unknown }>(),
    removed: props<{ id: string }>(),
    /** A different user signed in: drop the previous user's queue. */
    cleared: emptyProps(),
  },
});
