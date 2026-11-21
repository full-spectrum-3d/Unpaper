import { Question } from './form-definition';
import { gridRows } from './renderer-grid';

const q = (id: string, y: number, x = 0) =>
  ({ x, y, cols: 1, rows: 1, field: { id } }) as unknown as Question;

describe('gridRows', () => {
  it('closes the gap left by a hidden middle row', () => {
    const [a, b, c] = [q('a', 0), q('b', 1), q('c', 2)];
    expect(gridRows([a, b, c]).get(c)).toBe(3);
    const rows = gridRows([a, c]); // b is hidden
    expect([rows.get(a), rows.get(c)]).toEqual([1, 2]);
  });

  it('keeps items sharing a y on the same row', () => {
    const [a, b, c] = [q('a', 4, 0), q('b', 4, 1), q('c', 9)];
    const rows = gridRows([a, b, c]);
    expect([rows.get(a), rows.get(b), rows.get(c)]).toEqual([1, 1, 2]);
  });
});
