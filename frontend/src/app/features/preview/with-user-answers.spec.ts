import { FormDefinition, FormField } from './form-definition';
import { withUserAnswers } from './with-user-answers';

const field = (id: string, extra: Partial<FormField> = {}): FormField => ({
  id,
  type: 'TEXT_FIELD',
  techName: id,
  title: id,
  ...extra,
});
const def = (): FormDefinition => ({
  title: 't',
  flow: { links: [] },
  tabs: [
    {
      id: 'a',
      title: 'A',
      type: 'MAIN',
      questions: [
        {
          x: 0,
          y: 0,
          rows: 1,
          cols: 3,
          field: field('sec', {
            type: 'SECTION',
            repeatingSectionGrid: [{ x: 0, y: 0, rows: 1, cols: 1, field: field('inner') }],
          }),
        },
        { x: 0, y: 1, rows: 1, cols: 1, field: field('other') },
      ],
    },
  ],
});
const userAnswer = (f: FormField) => (f as unknown as Record<string, unknown>)['__userAnswer'];

describe('withUserAnswers', () => {
  it('inserts __userAnswer', () => {
    const out = withUserAnswers(
      def(),
      new Map<string, unknown>([
        ['sec', 'S'],
        ['inner', 'I'],
      ]),
    );
    expect(userAnswer(out.tabs[0].questions[0].field)).toBe('S');
    expect(userAnswer(out.tabs[0].questions[0].field.repeatingSectionGrid![0].field)).toBe('I');
  });

  it('does not mutate input', () => {
    const input = def();
    const before = structuredClone(input);
    withUserAnswers(input, new Map([['inner', 'I']]));
    expect(input).toEqual(before);
  });

  it('leaves fields without answers without the key', () => {
    const out = withUserAnswers(def(), new Map([['inner', 'I']]));
    expect('__userAnswer' in out.tabs[0].questions[1].field).toBe(false);
  });
});
