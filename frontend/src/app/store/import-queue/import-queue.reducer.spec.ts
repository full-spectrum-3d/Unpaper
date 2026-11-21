import { ImportQueueActions } from './import-queue.actions';
import { QueueItem, importQueueFeatureKey, importQueueReducer, initialImportQueueState } from './import-queue.reducer';
import { selectDoneItems, selectQueueCounts, selectQueueItems } from './import-queue.selectors';

const item = (id: string, over: Partial<QueueItem> = {}): QueueItem => ({
  id,
  name: `${id}.pdf`,
  size: 1,
  status: 'pending',
  error: null,
  retryable: false,
  result: null,
  startedAt: null,
  durationMs: null,
  ...over,
});

const withItems = (...items: QueueItem[]) =>
  importQueueReducer(initialImportQueueState, ImportQueueActions.filesAdded({ items }));

describe('importQueueReducer', () => {
  it('filesAdded keeps insertion order', () => {
    const state = withItems(item('b'), item('a'), item('c'));
    expect(state.ids).toEqual(['b', 'a', 'c']);
  });

  it('convertStarted sets processing and startedAt', () => {
    const state = importQueueReducer(withItems(item('a')), ImportQueueActions.convertStarted({ id: 'a', startedAt: 5 }));
    expect(state.entities['a']).toMatchObject({ status: 'processing', startedAt: 5 });
  });

  it('convertSucceeded sets done, result, durationMs, clears error', () => {
    const before = withItems(item('a', { status: 'processing', error: 'x' }));
    const state = importQueueReducer(
      before,
      ImportQueueActions.convertSucceeded({ id: 'a', result: { k: 1 }, durationMs: 9 }),
    );
    expect(state.entities['a']).toMatchObject({ status: 'done', result: { k: 1 }, durationMs: 9, error: null });
  });

  it('convertFailed sets error, message, retryable true', () => {
    const before = withItems(item('a', { status: 'processing' }));
    const state = importQueueReducer(before, ImportQueueActions.convertFailed({ id: 'a', error: 'boom' }));
    expect(state.entities['a']).toMatchObject({ status: 'error', error: 'boom', retryable: true });
  });

  it('retry only for retryable error', () => {
    const fixed = withItems(item('a', { status: 'error', error: 'x', retryable: false }));
    expect(importQueueReducer(fixed, ImportQueueActions.retry({ id: 'a' }))).toBe(fixed);
    const retryable = withItems(item('a', { status: 'error', error: 'x', retryable: true }));
    const state = importQueueReducer(retryable, ImportQueueActions.retry({ id: 'a' }));
    expect(state.entities['a']).toMatchObject({ status: 'pending', error: null });
  });

  it('removed deletes pending, error and done', () => {
    const before = withItems(
      item('a'),
      item('b', { status: 'error', error: 'x' }),
      item('c', { status: 'done' }),
    );
    const state = ['a', 'b', 'c'].reduce(
      (s, id) => importQueueReducer(s, ImportQueueActions.removed({ id })),
      before,
    );
    expect(state.ids).toEqual([]);
  });

  it('removed ignored while processing', () => {
    const before = withItems(item('a', { status: 'processing' }));
    expect(importQueueReducer(before, ImportQueueActions.removed({ id: 'a' }))).toBe(before);
  });
});

describe('importQueue selectors', () => {
  const root = {
    [importQueueFeatureKey]: withItems(
      item('a'),
      item('b', { status: 'processing' }),
      item('c', { status: 'done' }),
      item('d', { status: 'error' }),
      item('e', { status: 'done' }),
    ),
  };

  it('counts for a mixed queue', () => {
    expect(selectQueueCounts(root)).toEqual({ total: 5, done: 2, error: 1, processing: 1, pending: 1 });
    expect(selectQueueItems(root).length).toBe(5);
  });

  it('selectDoneItems returns only done', () => {
    expect(selectDoneItems(root).map((i) => i.id)).toEqual(['c', 'e']);
  });
});
