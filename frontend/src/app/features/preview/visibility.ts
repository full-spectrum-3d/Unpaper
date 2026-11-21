import jsonata from 'jsonata';
import { FormDefinition, FormField, Question } from './form-definition';
import { withUserAnswers } from './with-user-answers';

/** Compiled queries; a failed compile is cached as null so a broken query warns once. */
const compiled = new Map<string, jsonata.Expression | null>();

const truthy = (r: unknown): boolean => r === true || (Array.isArray(r) && r.includes(true));

/** Fail-open: a query that does not compile or evaluate counts as "no opinion" (null), with a warning. */
async function run(field: FormField, query: string, input: unknown): Promise<boolean | null> {
  try {
    if (!compiled.has(query)) {
      try {
        compiled.set(query, jsonata(query));
      } catch (e) {
        compiled.set(query, null);
        throw e;
      }
    }
    const expr = compiled.get(query);
    if (!expr) return null;
    return truthy(await expr.evaluate(input));
  } catch (e) {
    console.warn(`Visibility query failed for field "${field.techName}"`, e);
    return null;
  }
}

async function isVisible(field: FormField, input: unknown): Promise<boolean> {
  const states = field.states ?? [];
  const show = states.filter((s) => s.type === 'SHOW');
  const hide = states.filter((s) => s.type === 'HIDE');
  const [shows, hides] = await Promise.all([
    Promise.all(show.map((s) => run(field, s.query, input))),
    Promise.all(hide.map((s) => run(field, s.query, input))),
  ]);
  const shown = shows.length === 0 || shows.some((r) => r !== false);
  return shown && !hides.some((r) => r === true);
}

/** Ids of hidden fields; hiding a section hides all its descendants. */
export async function evaluateVisibility(
  def: FormDefinition,
  answers: ReadonlyMap<string, unknown>,
): Promise<ReadonlySet<string>> {
  const input = withUserAnswers(def, answers);
  const hidden = new Set<string>();
  const collect = (field: FormField) => {
    hidden.add(field.id);
    (field.repeatingSectionGrid ?? []).forEach((q) => collect(q.field));
  };
  const visit = async (qs: Question[]): Promise<void> => {
    await Promise.all(
      qs.map(async ({ field }) => {
        if (!(await isVisible(field, input))) collect(field);
        else await visit(field.repeatingSectionGrid ?? []);
      }),
    );
  };
  await Promise.all(def.tabs.map((t) => visit(t.questions)));
  return hidden;
}
