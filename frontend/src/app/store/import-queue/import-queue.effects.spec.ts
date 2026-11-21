import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideMockActions } from '@ngrx/effects/testing';
import { Action } from '@ngrx/store';
import { MockStore, provideMockStore } from '@ngrx/store/testing';
import { Observable, of, Subject, throwError } from 'rxjs';
import { CONVERT_FILE, ConvertFileFn } from '../../features/import/convert-file';
import { FileRegistry } from '../../features/import/file-registry';
import { ImportQueueActions as A } from './import-queue.actions';
import { ImportQueueEffects } from './import-queue.effects';
import { QueueItem, importQueueFeatureKey } from './import-queue.reducer';

const item = (id: string, status: QueueItem['status']): QueueItem => ({
  id,
  name: `${id}.pdf`,
  size: 1,
  status,
  error: null,
  retryable: true,
  result: null,
  startedAt: null,
  durationMs: null,
});

const running = (id: string, startedAt = 0): QueueItem => ({ ...item(id, 'processing'), startedAt });
const tick = () => new Promise((r) => setTimeout(r));

const stateOf = (items: QueueItem[]) => ({
  [importQueueFeatureKey]: {
    ids: items.map((i) => i.id),
    entities: Object.fromEntries(items.map((i) => [i.id, i])),
  },
});

function setup(items: QueueItem[], convert: ConvertFileFn = () => of({ ok: 1 })) {
  const actions$ = new Subject<Action>();
  TestBed.configureTestingModule({
    providers: [
      ImportQueueEffects,
      provideMockActions(() => actions$),
      provideMockStore({ initialState: stateOf(items) }),
      { provide: CONVERT_FILE, useValue: convert },
    ],
  });
  const effects = TestBed.inject(ImportQueueEffects);
  const registry = TestBed.inject(FileRegistry);
  const out: Action[] = [];
  effects.schedule$.subscribe((a) => out.push(a));
  effects.convert$.subscribe((a) => out.push(a));
  return { actions$, out, registry, effects, store: TestBed.inject(MockStore) };
}

describe('ImportQueueEffects', () => {
  it('schedule starts up to two pending', async () => {
    const { actions$, out } = setup([item('1', 'pending'), item('2', 'pending'), item('3', 'pending')]);
    actions$.next(A.filesAdded({ items: [] }));
    await tick();
    const started = out.filter((a) => a.type === A.convertStarted.type) as ReturnType<
      typeof A.convertStarted
    >[];
    expect(started.map((a) => a.id)).toEqual(['1', '2']);
  });

  it('schedule starts next after success', async () => {
    const { actions$, out } = setup([item('1', 'processing'), item('2', 'pending'), item('3', 'pending')]);
    actions$.next(A.convertSucceeded({ id: '0', result: {}, durationMs: 1 }));
    await tick();
    const started = out.filter((a) => a.type === A.convertStarted.type) as ReturnType<
      typeof A.convertStarted
    >[];
    expect(started.map((a) => a.id)).toEqual(['2']);
  });

  it('removed pending is never started', async () => {
    const { actions$, out } = setup([item('2', 'pending')]);
    actions$.next(A.removed({ id: '1' }));
    await tick();
    expect(out.map((a) => (a as { id?: string }).id)).toEqual(['2']);
  });

  it('retry triggers schedule', async () => {
    const { actions$, out } = setup([item('1', 'pending')]);
    actions$.next(A.retry({ id: '1' }));
    await tick();
    expect(out[0].type).toBe(A.convertStarted.type);
  });

  it('convert succeeds', () => {
    const { actions$, out, registry } = setup([running('1', 5)]);
    registry.add('1', new File(['x'], '1.pdf'));
    actions$.next(A.convertStarted({ id: '1', startedAt: 5 }));
    const done = out[0] as ReturnType<typeof A.convertSucceeded>;
    expect(done.type).toBe(A.convertSucceeded.type);
    expect(done.result).toEqual({ ok: 1 });
    expect(done.durationMs).toBeGreaterThanOrEqual(0);
  });

  it('convert fails with user message', () => {
    const err = new HttpErrorResponse({ status: 503, error: { code: 'LLM_UNAVAILABLE' } });
    const { actions$, out, registry } = setup([running('1')], () => throwError(() => err) as Observable<never>);
    registry.add('1', new File(['x'], '1.pdf'));
    actions$.next(A.convertStarted({ id: '1', startedAt: 0 }));
    expect(out[0]).toEqual(
      A.convertFailed({
        id: '1',
        error: 'Usługa analizy formularzy jest chwilowo niedostępna. Spróbuj ponownie.',
      }),
    );
  });

  it('missing file fails', () => {
    const { actions$, out } = setup([running('x')]);
    actions$.next(A.convertStarted({ id: 'x', startedAt: 0 }));
    expect(out[0]).toEqual(A.convertFailed({ id: 'x', error: 'Plik niedostępny – dodaj go ponownie' }));
  });

  it('ignores a start that did not move the item to processing', () => {
    const convert = vi.fn(() => of({}));
    const { actions$, out, registry } = setup([item('1', 'done')], convert);
    registry.add('1', new File(['x'], '1.pdf'));
    actions$.next(A.convertStarted({ id: '1', startedAt: 0 }));
    expect(convert).not.toHaveBeenCalled();
    expect(out).toEqual([]);
  });

  it('success releases file from registry', () => {
    const { actions$, registry } = setup([running('1')]);
    registry.add('1', new File(['x'], '1.pdf'));
    actions$.next(A.convertStarted({ id: '1', startedAt: 0 }));
    expect(registry.get('1')).toBeUndefined();
  });
});
