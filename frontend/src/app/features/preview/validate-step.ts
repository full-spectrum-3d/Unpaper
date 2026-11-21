import { KNOWN_FIELD_TYPES, FormField, Question } from './form-definition';
import { isCascade, selectOptions } from './select-options';
import { validateField } from './validators';

const NO_ANSWER = new Set(['SECTION', 'TEXT_BLOCK']);
const KNOWN = new Set<string>(KNOWN_FIELD_TYPES);

/** Unknown types have no control and an option-less SELECT cannot be filled: never block on those. */
const fillable = (field: FormField) =>
  KNOWN.has(field.type) &&
  !NO_ANSWER.has(field.type) &&
  !(field.type === 'SELECT' && !isCascade(field) && !selectOptions(field).length);

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
      if (fillable(field) && !field.readOnly && !readOnly.has(field.id)) {
        const error = validateField(field, answers.get(field.id));
        if (error) errors.set(field.id, error);
      }
      visit(field.repeatingSectionGrid ?? []);
    });
  visit(questions);
  return errors;
}
