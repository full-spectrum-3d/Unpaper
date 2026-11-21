import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { FormDefinition, FormTab, Question } from './form-definition';
import { orderTabs, sortQuestions } from './page-order';

const tab = (id: string, type: 'MAIN' | 'FINISH' = 'MAIN'): FormTab => ({
  id,
  title: id,
  type,
  questions: [],
});
const def = (tabs: FormTab[], links: [string, string][]): FormDefinition => ({
  title: 't',
  tabs,
  flow: { links: links.map(([source, target]) => ({ source, target })) },
});
const ids = (d: FormDefinition) => orderTabs(d).map((t) => t.id);

describe('orderTabs', () => {
  it('orders by flow links', () => {
    expect(orderTabs(nadplata as unknown as FormDefinition).map((t) => t.title)).toEqual([
      'Dane',
      'Informacje o nadpłacie',
      'Kontakt i zgody',
      'Strona końcowa',
    ]);
  });

  it('starts at tab without incoming link', () => {
    const d = nadplata as unknown as FormDefinition;
    const reversed = { ...d, tabs: [...d.tabs].reverse() };
    expect(orderTabs(reversed).map((t) => t.title)).toEqual(orderTabs(d).map((t) => t.title));
  });

  it('no links keeps array order with FINISH last', () => {
    expect(ids(def([tab('F', 'FINISH'), tab('A'), tab('B')], []))).toEqual(['A', 'B', 'F']);
  });

  it('breaks cycles', () => {
    expect(
      ids(
        def(
          [tab('A'), tab('B')],
          [
            ['A', 'B'],
            ['B', 'A'],
          ],
        ),
      ),
    ).toEqual(['A', 'B']);
  });

  it('ignores dangling links', () => {
    expect(
      ids(
        def(
          [tab('A'), tab('B')],
          [
            ['A', 'X'],
            ['Y', 'B'],
          ],
        ),
      ),
    ).toEqual(['A', 'B']);
  });

  it('appends unreachable tabs', () => {
    expect(ids(def([tab('A'), tab('B'), tab('C'), tab('F', 'FINISH')], [['A', 'B']]))).toEqual([
      'A',
      'B',
      'C',
      'F',
    ]);
  });
});

describe('sortQuestions', () => {
  it('sorts by y then x without mutating', () => {
    const q = (x: number, y: number) => ({ x, y }) as Question;
    const input = [q(1, 1), q(0, 1), q(2, 0)];
    expect(sortQuestions(input).map((s) => [s.x, s.y])).toEqual([
      [2, 0],
      [0, 1],
      [1, 1],
    ]);
    expect(input[0].x).toBe(1);
  });
});
