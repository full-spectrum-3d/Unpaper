import { AuthActions } from '../auth/auth.actions';
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
  report: null,
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

  it('ignores start, success and failure for items in the wrong status', () => {
    const { convertStarted, convertSucceeded, convertFailed } = ImportQueueActions;
    const processing = withItems(item('a', { status: 'processing' }));
    expect(importQueueReducer(processing, convertStarted({ id: 'a', startedAt: 1 }))).toBe(processing);
    const pending = withItems(item('a'));
    expect(importQueueReducer(pending, convertSucceeded({ id: 'a', result: 1, report: null, durationMs: 1 }))).toBe(pending);
    expect(importQueueReducer(pending, convertFailed({ id: 'a', error: 'x' }))).toBe(pending);
  });

  it('convertSucceeded sets done, result, durationMs, clears error', () => {
    const before = withItems(item('a', { status: 'processing', error: 'x' }));
    const state = importQueueReducer(
      before,
      ImportQueueActions.convertSucceeded({ id: 'a', result: { k: 1 }, report: { w: 1 }, durationMs: 9 }),
    );
    expect(state.entities['a']).toMatchObject({ status: 'done', result: { k: 1 }, report: { w: 1 }, durationMs: 9, error: null });
  });

  it('cancelled turns a processing item into a retryable error and ignores other statuses', () => {
    const processing = withItems(item('a', { status: 'processing' }));
    const state = importQueueReducer(processing, ImportQueueActions.cancelled({ id: 'a' }));
    expect(state.entities['a']).toMatchObject({ status: 'error', error: 'Analiza anulowana', retryable: true });
    const done = withItems(item('a', { status: 'done' }));
    expect(importQueueReducer(done, ImportQueueActions.cancelled({ id: 'a' }))).toBe(done);
  });

  it('warningAccepted records each key once on a done item; warningsRestored clears them', () => {
    const { warningAccepted, warningsRestored } = ImportQueueActions;
    let state = withItems(item('a', { status: 'done' }));
    state = importQueueReducer(state, warningAccepted({ id: 'a', key: 'k1' }));
    state = importQueueReducer(state, warningAccepted({ id: 'a', key: 'k2' }));
    expect(importQueueReducer(state, warningAccepted({ id: 'a', key: 'k1' }))).toBe(state);
    expect(state.entities['a']?.acceptedWarnings).toEqual(['k1', 'k2']);
    expect(importQueueReducer(state, warningsRestored({ id: 'a' })).entities['a']?.acceptedWarnings).toEqual([]);
    const pending = withItems(item('b'));
    expect(importQueueReducer(pending, warningAccepted({ id: 'b', key: 'k' }))).toBe(pending);
  });

  it('convertFailed sets error, message, retryable true', () => {
    const before = withItems(item('a', { status: 'processing' }));
    const state = importQueueReducer(before, ImportQueueActions.convertFailed({ id: 'a', error: 'boom' }));
    expect(state.entities['a']).toMatchObject({ status: 'error', error: 'boom', retryable: true });
  });

  it('convertFailed stores passwordState, defaulting to null', () => {
    const before = withItems(item('a', { status: 'processing' }));
    const asked = importQueueReducer(
      before,
      ImportQueueActions.convertFailed({ id: 'a', error: 'x', passwordState: 'required' }),
    );
    expect(asked.entities['a']).toMatchObject({ status: 'error', passwordState: 'required' });
    const plain = importQueueReducer(before, ImportQueueActions.convertFailed({ id: 'a', error: 'x' }));
    expect(plain.entities['a']?.passwordState).toBeNull();
  });

  it('passwordSubmitted re-queues only a password error', () => {
    const asked = withItems(item('a', { status: 'error', error: 'x', retryable: true, passwordState: 'invalid' }));
    const state = importQueueReducer(asked, ImportQueueActions.passwordSubmitted({ id: 'a' }));
    expect(state.entities['a']).toMatchObject({ status: 'pending', error: null, passwordState: null });
    const other = withItems(item('a', { status: 'error', error: 'x', retryable: true }));
    expect(importQueueReducer(other, ImportQueueActions.passwordSubmitted({ id: 'a' }))).toBe(other);
  });

  it('retry only for retryable error', () => {
    const fixed = withItems(item('a', { status: 'error', error: 'x', retryable: false }));
    expect(importQueueReducer(fixed, ImportQueueActions.retry({ id: 'a' }))).toBe(fixed);
    const retryable = withItems(item('a', { status: 'error', error: 'x', retryable: true, passwordState: 'required' }));
    const state = importQueueReducer(retryable, ImportQueueActions.retry({ id: 'a' }));
    expect(state.entities['a']).toMatchObject({ status: 'pending', error: null, passwordState: null });
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

describe('importQueueReducer session handling', () => {
  it('manual logout clears the queue', () => {
    const state = importQueueReducer(withItems(item('1'), item('2')), AuthActions.logout({ reason: 'manual' }));
    expect(state.ids).toEqual([]);
  });

  it.each(['expired', 'unauthorized'] as const)('%s logout keeps the queue', (reason) => {
    const before = withItems(item('1'));
    expect(importQueueReducer(before, AuthActions.logout({ reason }))).toBe(before);
  });

  it('resultEdited replaces the result of a done item, keeps the report and marks it edited', () => {
    const { resultEdited, convertSucceeded } = ImportQueueActions;
    const done = withItems(item('a', { status: 'done', result: { v: 1 }, report: { r: 1 } }));
    const edited = importQueueReducer(done, resultEdited({ id: 'a', result: { v: 2 } }));
    expect(edited.entities['a']).toMatchObject({ result: { v: 2 }, report: { r: 1 }, edited: true });
    const pending = withItems(item('a'));
    expect(importQueueReducer(pending, resultEdited({ id: 'a', result: {} }))).toBe(pending);
    // A fresh conversion clears the flag.
    const reconverted = importQueueReducer(
      withItems(item('c', { status: 'processing', edited: true })),
      convertSucceeded({ id: 'c', result: {}, report: null, durationMs: 1 }),
    );
    expect(reconverted.entities['c']!.edited).toBe(false);
  });

  it('late result for a cleared item is a no-op', () => {
    const cleared = importQueueReducer(withItems(item('1', { status: 'processing' })), ImportQueueActions.cleared());
    expect(importQueueReducer(cleared, ImportQueueActions.convertSucceeded({ id: '1', result: {}, report: null, durationMs: 1 }))).toBe(cleared);
  });
});
