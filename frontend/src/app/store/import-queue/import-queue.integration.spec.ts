import { TestBed } from '@angular/core/testing';
import { provideEffects } from '@ngrx/effects';
import { ScannedActionsSubject, Store, provideStore } from '@ngrx/store';
import { defer, finalize, map, of, timer } from 'rxjs';
import { CONVERT_FILE, ConvertFileFn } from '../../features/import/convert-file';
import { FileRegistry } from '../../features/import/file-registry';
import { ImportQueueActions } from './import-queue.actions';
import { ImportQueueEffects } from './import-queue.effects';
import { authFeatureKey, authReducer } from '../auth/auth.reducer';
import { AuthActions } from '../auth/auth.actions';
import { QueueItem, importQueueFeatureKey, importQueueReducer } from './import-queue.reducer';
import { selectQueueCounts, selectQueueItems } from './import-queue.selectors';

const pending = (id: string): QueueItem => ({
  id,
  name: `${id}.pdf`,
  size: 1,
  status: 'pending',
  error: null,
  retryable: true,
  result: null,
  startedAt: null,
  durationMs: null,
});

function setup(convert: ConvertFileFn, ids: string[], withFile: (id: string) => boolean = () => true) {
  TestBed.configureTestingModule({
    providers: [
      provideStore({ [importQueueFeatureKey]: importQueueReducer, [authFeatureKey]: authReducer }),
      provideEffects(ImportQueueEffects),
      { provide: CONVERT_FILE, useValue: convert },
    ],
  });
  const store = TestBed.inject(Store);
  const registry = TestBed.inject(FileRegistry);
  store.dispatch(AuthActions.loginSuccess({ token: 't', expiresAt: Date.now() + 1e6, username: 'u' }));
  const started: string[] = [];
  TestBed.inject(ScannedActionsSubject).subscribe((a) => {
    if (a.type === ImportQueueActions.convertStarted.type) started.push((a as unknown as { id: string }).id);
  });
  ids.filter(withFile).forEach((id) => registry.add(id, new File(['x'], `${id}.pdf`)));
  store.dispatch(ImportQueueActions.filesAdded({ items: ids.map(pending) }));
  return { store, started };
}

describe('import queue integration', () => {
  it('never more than two conversions active, each file converted once', async () => {
    vi.useFakeTimers();
    try {
      let active = 0;
      let max = 0;
      const calls: string[] = [];
      const convert: ConvertFileFn = (file) =>
        defer(() => {
          calls.push(file.name);
          max = Math.max(max, ++active);
          return timer(1000).pipe(map(() => ({})));
        }).pipe(finalize(() => active--));
      const ids = Array.from({ length: 10 }, (_, i) => String(i));
      const { store } = setup(convert, ids);
      const counts = store.selectSignal(selectQueueCounts);
      await vi.advanceTimersByTimeAsync(0);
      for (let t = 0; t < 6000; t += 100) {
        expect(counts().processing).toBeLessThanOrEqual(2);
        await vi.advanceTimersByTimeAsync(100);
      }
      expect(counts().done).toBe(10);
      expect(max).toBeLessThanOrEqual(2);
      expect(calls).toHaveLength(10);
    } finally {
      vi.useRealTimers();
    }
  });

  it('synchronously completing conversions never start a file twice', async () => {
    const calls: string[] = [];
    const convert: ConvertFileFn = (file) => {
      calls.push(file.name);
      return of({});
    };
    const { store, started } = setup(convert, ['1', '2', '3', '4'], (id) => id > '2');
    await new Promise((r) => setTimeout(r));
    expect(started.sort()).toEqual(['1', '2', '3', '4']);
    expect(calls.sort()).toEqual(['3.pdf', '4.pdf']);
    const status = Object.fromEntries(store.selectSignal(selectQueueItems)().map((i) => [i.id, i.status]));
    expect(status).toEqual({ 1: 'error', 2: 'error', 3: 'done', 4: 'done' });
  });
});
