import { downloadBlob, downloadJson } from './download';

describe('download', () => {
  let create: ReturnType<typeof vi.fn>;
  let revoke: ReturnType<typeof vi.fn>;
  let names: (string | null)[];

  beforeEach(() => {
    vi.useFakeTimers();
    names = [];
    create = vi.fn(() => 'blob:x');
    revoke = vi.fn();
    URL.createObjectURL = create as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revoke as unknown as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.getAttribute('download'));
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('downloadBlob clicks a named anchor and revokes the URL later', () => {
    downloadBlob(new Blob(['x']), 'a.zip');
    expect(names).toEqual(['a.zip']);
    expect(revoke).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(revoke).toHaveBeenCalledWith('blob:x');
    expect(document.querySelector('a[download]')).toBeNull();
  });

  it('downloadJson pretty-prints with 2 spaces', async () => {
    downloadJson({ a: 1 }, 'a.json');
    const blob = create.mock.calls[0][0] as Blob;
    expect(await blob.text()).toBe('{\n  "a": 1\n}');
    expect(names).toEqual(['a.json']);
  });
});
