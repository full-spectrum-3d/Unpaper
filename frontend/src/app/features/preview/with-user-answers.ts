import { FormDefinition, Question } from './form-definition';

/**
 * Deep copy of the definition with `__userAnswer` on every field that has an answer (input for jsonata).
 * Hidden fields get none: their stale answers must not keep dependent fields visible.
 */
export function withUserAnswers(
  def: FormDefinition,
  answers: ReadonlyMap<string, unknown>,
  hidden: ReadonlySet<string> = new Set(),
): FormDefinition {
  const copy = structuredClone(def);
  const visit = (qs: Question[]) =>
    qs.forEach(({ field }) => {
      if (answers.has(field.id) && !hidden.has(field.id))
        Object.assign(field, { __userAnswer: answers.get(field.id) });
      visit(field.repeatingSectionGrid ?? []);
    });
  copy.tabs.forEach((t) => visit(t.questions));
  return copy;
}
