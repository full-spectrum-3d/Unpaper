import { Question } from './form-definition';
import { validateField } from './validators';

const NO_ANSWER = new Set(['SECTION', 'TEXT_BLOCK']);

/** Errors of the visible, editable fields of a step, keyed by field id, in question order. */
export function validateStep(
  questions: Question[],
  answers: ReadonlyMap<string, unknown>,
  hidden: ReadonlySet<string>,
  readOnly: ReadonlySet<string>,
): Map<string, string> {
  const errors = new Map<string, string>();
  const visit = (qs: Question[]) =>
    qs.forEach(({ field }) => {
      if (hidden.has(field.id)) return;
      if (!NO_ANSWER.has(field.type) && !field.readOnly && !readOnly.has(field.id)) {
        const error = validateField(field, answers.get(field.id));
        if (error) errors.set(field.id, error);
      }
      visit(field.repeatingSectionGrid ?? []);
    });
  visit(questions);
  return errors;
}
