import { TestBed } from '@angular/core/testing';
import { provideEffects } from '@ngrx/effects';
import { Store, provideStore } from '@ngrx/store';
import { map, timer } from 'rxjs';
import { CONVERT_FILE } from '../../features/import/convert-file';
import { FileRegistry } from '../../features/import/file-registry';
import { ImportQueueActions } from './import-queue.actions';
import { ImportQueueEffects } from './import-queue.effects';
import { importQueueFeatureKey, importQueueReducer } from './import-queue.reducer';
import { selectQueueCounts } from './import-queue.selectors';

describe('import queue integration', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('never more than two processing', () => {
    TestBed.configureTestingModule({
      providers: [
        provideStore({ [importQueueFeatureKey]: importQueueReducer }),
        provideEffects(ImportQueueEffects),
        { provide: CONVERT_FILE, useValue: () => timer(1000).pipe(map(() => ({}))) },
      ],
    });
    const store = TestBed.inject(Store);
    const registry = TestBed.inject(FileRegistry);
    const items = Array.from({ length: 10 }, (_, i) => {
      const id = String(i);
      registry.add(id, new File(['x'], `${id}.pdf`));
      return {
        id, name: `${id}.pdf`, size: 1, status: 'pending' as const, error: null,
        retryable: true, result: null, startedAt: null, durationMs: null,
      };
    });
    const counts = store.selectSignal(selectQueueCounts);
    store.dispatch(ImportQueueActions.filesAdded({ items }));
    for (let t = 0; t < 6000; t += 100) {
      expect(counts().processing).toBeLessThanOrEqual(2);
      vi.advanceTimersByTime(100);
    }
    expect(counts().done).toBe(10);
  });
});
