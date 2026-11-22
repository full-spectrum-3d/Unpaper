import { FieldOption, FormDefinition, FormField, Question } from '../preview/form-definition';

/** Types the editor can create or switch to, with their labels in the UI. */
export const EDITABLE_TYPES = {
  TEXT_FIELD: 'Tekst',
  TEXTAREA: 'Długi tekst',
  NUMBER: 'Liczba',
  DATEPICKER: 'Data',
  RADIO: 'Jednokrotny wybór',
  SELECT: 'Lista',
  CHECKBOX: 'Wielokrotny wybór',
  FILE_UPLOADER: 'Plik',
} as const;
export type EditableType = keyof typeof EDITABLE_TYPES;

export const isEditableType = (type: string): type is EditableType => type in EDITABLE_TYPES;
export const isSection = (f: FormField): boolean =>
  f.type === 'SECTION' || f.type === 'REPEATING_SECTION';
export const isChoice = (type: string): boolean =>
  type === 'RADIO' || type === 'SELECT' || type === 'CHECKBOX';
/** Registry fields keep their data source and validators: the editor shows them read-only. */
export const isRegistryField = (f: FormField): boolean =>
  f.readOnly === true || f.defaultValueType === 'EXTERNAL_SYSTEM';
/** Backend rule R09: a choice field without a dictionary needs this many options. */
export const minOptions = (type: string): number =>
  type === 'CHECKBOX' ? 1 : isChoice(type) ? 2 : 0;

/** Mirrors ALLOWED_VALIDATORS in backend app/models/form.py: TEXT_FIELD takes all, other inputs only REQUIRED. */
const allowsValidator = (type: string, validator: string): boolean =>
  type === 'TEXT_FIELD' || (isEditableType(type) && validator === 'REQUIRED');

const TECH_NAME_MAX = 60;

/** Same rules as backend build/fields.py slugify: ASCII [a-z0-9_], Polish letters transliterated. */
export function slugify(text: string, maxLength = TECH_NAME_MAX): string {
  const ascii = text
    .toLowerCase()
    .replace(/ł/g, 'l') // NFKD does not decompose ł
    .normalize('NFKD')
    .replace(/\p{M}/gu, '');
  let slug = ascii.replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  if (slug.length > maxLength) {
    let cut = slug.slice(0, maxLength);
    const idx = cut.lastIndexOf('_');
    if (idx >= maxLength / 2) cut = cut.slice(0, idx);
    slug = cut.replace(/^_+|_+$/g, '');
  }
  return slug || 'pole';
}

export function* allQuestions(qs: readonly Question[]): Generator<Question> {
  for (const q of qs) {
    yield q;
    yield* allQuestions(q.field.repeatingSectionGrid ?? []);
  }
}
const allFields = (def: FormDefinition): FormField[] =>
  def.tabs.flatMap((t) => [...allQuestions(t.questions)].map((q) => q.field));

function uniqueTechName(def: FormDefinition, title: string): string {
  const taken = new Set(allFields(def).map((f) => f.techName));
  const base = slugify(title);
  let name = base;
  for (let n = 2; taken.has(name); n++) {
    const suffix = `_${n}`;
    name = base.slice(0, TECH_NAME_MAX - suffix.length) + suffix;
  }
  return name;
}

/** Keeps option objects (and their ids) whose name did not change. */
function toOptions(names: readonly string[], existing: readonly FieldOption[] = []): FieldOption[] {
  return names.map(
    (name) =>
      existing.find((o) => o.name === name) ?? {
        id: crypto.randomUUID(),
        name,
        techName: slugify(name),
      },
  );
}

/**
 * Maps every question (depth first) with structural sharing: untouched tabs and questions keep their identity.
 * `fn` returning null removes the question together with its children.
 */
function mapQuestions(def: FormDefinition, fn: (q: Question) => Question | null): FormDefinition {
  const mapGrid = (qs: Question[]): Question[] => {
    let changed = false;
    const out: Question[] = [];
    for (const q of qs) {
      let next = fn(q);
      const grid = next?.field.repeatingSectionGrid;
      if (next && grid?.length) {
        const mapped = mapGrid(grid);
        if (mapped !== grid)
          next = { ...next, field: { ...next.field, repeatingSectionGrid: mapped } };
      }
      if (next !== q) changed = true;
      if (next) out.push(next);
    }
    return changed ? out : qs;
  };
  let changed = false;
  const tabs = def.tabs.map((t) => {
    const questions = mapGrid(t.questions);
    if (questions === t.questions) return t;
    changed = true;
    return { ...t, questions };
  });
  return changed ? { ...def, tabs } : def;
}

const updateById = (def: FormDefinition, id: string, fn: (f: FormField) => FormField) =>
  mapQuestions(def, (q) => (q.field.id === id ? { ...q, field: fn(q.field) } : q));

export interface NewField {
  type: EditableType;
  title: string;
  required: boolean;
  /** Option names, used for choice types only. */
  options?: readonly string[];
}

/** Appends a field at the end of a section (backend rule R03: inputs live only inside sections). */
export function addField(
  def: FormDefinition,
  sectionId: string,
  input: NewField,
): { definition: FormDefinition; field: FormField } {
  const title = input.title.trim();
  const field: FormField = {
    id: crypto.randomUUID(),
    type: input.type,
    techName: uniqueTechName(def, title),
    title,
    description: '',
    options: isChoice(input.type) ? toOptions(input.options ?? []) : [],
    validation: input.required ? ['REQUIRED'] : [],
    readOnly: false,
    repeatingSectionGrid: [],
    states: [],
    questionOrder: 0,
    tooltipMessage: '',
  };
  const definition = updateById(def, sectionId, (section) => {
    const grid = section.repeatingSectionGrid ?? [];
    const y = Math.max(0, ...grid.map((q) => q.y + q.rows));
    const question: Question = { x: 0, y, rows: 1, cols: 3, field: { ...field, questionOrder: y } };
    return { ...section, repeatingSectionGrid: [...grid, question] };
  });
  return { definition, field };
}

export interface FieldPatch {
  title?: string;
  type?: EditableType;
  required?: boolean;
  options?: readonly string[];
}

const CHOICE_ONLY_KEYS = [
  'dictionaryName',
  'searchEnabled',
  'multiLevelTree',
  'selectAllEnabled',
] as const;

/** Changes label, type, requiredness or options; validators and options follow what the type allows. */
export function updateField(def: FormDefinition, id: string, patch: FieldPatch): FormDefinition {
  return updateById(def, id, (f) => {
    const next: FormField & Record<string, unknown> = { ...f };
    if (patch.title !== undefined) next.title = patch.title.trim();
    if (patch.type !== undefined && patch.type !== f.type) {
      next.type = patch.type;
      // A default typed for the old control may not fit the new one.
      delete next.defaultValue;
      if (!isChoice(patch.type)) {
        next.options = [];
        for (const key of CHOICE_ONLY_KEYS) delete next[key];
      }
    }
    let validation = (f.validation ?? []).filter((v) => allowsValidator(next.type, v));
    if (patch.required !== undefined) {
      validation = validation.filter((v) => v !== 'REQUIRED');
      if (patch.required && allowsValidator(next.type, 'REQUIRED')) validation.unshift('REQUIRED');
    }
    next.validation = validation;
    if (isChoice(next.type) && !next.dictionaryName) {
      const names = [...(patch.options ?? (next.options ?? []).map((o) => o.name))];
      // Placeholders keep a retyped field valid (backend rule R09) until the user names the options.
      while (names.length < minOptions(next.type)) names.push(`Opcja ${names.length + 1}`);
      next.options = toOptions(names, f.options);
    }
    return next;
  });
}

/** A visibility condition that names a removed field by techName; it would no longer compile on import. */
const referencesAny = (query: string, names: ReadonlySet<string>): boolean =>
  [...names].some((n) => query.includes(`'${n}'`) || query.includes(`"${n}"`));

/**
 * Removes a field (a section with its children) and the visibility conditions that referred to it.
 * Returns the fields that lost a condition so the UI can tell the user.
 */
export function removeField(
  def: FormDefinition,
  id: string,
): { definition: FormDefinition; droppedStatesOf: FormField[] } {
  const removed = new Set<string>();
  let definition = mapQuestions(def, (q) => {
    if (q.field.id !== id) return q;
    for (const r of allQuestions([q])) removed.add(r.field.techName);
    return null;
  });
  const droppedStatesOf: FormField[] = [];
  definition = mapQuestions(definition, (q) => {
    const states = q.field.states ?? [];
    const kept = states.filter((s) => !referencesAny(s.query, removed));
    if (kept.length === states.length) return q;
    droppedStatesOf.push(q.field);
    return { ...q, field: { ...q.field, states: kept } };
  });
  return { definition, droppedStatesOf };
}

/** One option per line; blank lines and repeats are dropped. */
export const parseOptions = (text: string): string[] => [
  ...new Set(
    text
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
  ),
];

export function optionsError(type: string, names: readonly string[]): string | null {
  const min = minOptions(type);
  if (names.length >= min) return null;
  return min === 1 ? 'Podaj co najmniej 1 opcję.' : `Podaj co najmniej ${min} opcje.`;
}

const STATIC_TYPE_LABELS: Record<string, string> = {
  SECTION: 'Sekcja',
  REPEATING_SECTION: 'Sekcja powtarzalna',
  INFO_SECTION: 'Informacja',
  TEXT_BLOCK: 'Blok tekstu',
  CONSENT_SECTION: 'Zgody',
};
export const typeLabel = (type: string): string =>
  (EDITABLE_TYPES as Record<string, string>)[type] ?? STATIC_TYPE_LABELS[type] ?? type;
