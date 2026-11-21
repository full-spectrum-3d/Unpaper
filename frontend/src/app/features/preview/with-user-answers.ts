import { FormDefinition, Question } from './form-definition';

/** Deep copy of the definition with `__userAnswer` on every field that has an answer (input for jsonata). */
export function withUserAnswers(
  def: FormDefinition,
  answers: ReadonlyMap<string, unknown>,
): FormDefinition {
  const copy = structuredClone(def);
  const visit = (qs: Question[]) =>
    qs.forEach(({ field }) => {
      if (answers.has(field.id)) Object.assign(field, { __userAnswer: answers.get(field.id) });
      visit(field.repeatingSectionGrid ?? []);
    });
  copy.tabs.forEach((t) => visit(t.questions));
  return copy;
}
