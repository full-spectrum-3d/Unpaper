import {
  FieldOption,
  FieldState,
  FormDefinition,
  FormField,
  Question,
} from '../preview/form-definition';
import { sortQuestions } from '../preview/page-order';

/** Types the editor can create or switch to, with their labels in the UI. */
export const EDITABLE_TYPES = {
  TEXT_FIELD: 'Tekst',
  TEXTAREA: 'Długi tekst',
  NUMBER: 'Liczba',
  DATEPICKER: 'Data',
  RADIO: 'Jednokrotny wybór',
  SELECT: 'Lista rozwijana',
  CHECKBOX: 'Wielokrotny wybór',
  FILE_UPLOADER: 'Plik',
  TEXT_BLOCK: 'Blok tekstu',
  INFO_SECTION: 'Sekcja informacyjna',
  CONSENT_SECTION: 'Sekcja zgód',
} as const;
export type EditableType = keyof typeof EDITABLE_TYPES;

export const isEditableType = (type: string): type is EditableType => type in EDITABLE_TYPES;
export const isSection = (f: FormField): boolean =>
  f.type === 'SECTION' || f.type === 'REPEATING_SECTION';
export const isChoice = (type: string): boolean =>
  type === 'RADIO' || type === 'SELECT' || type === 'CHECKBOX';
/** Static text shown to the user (body in `description`); backend rule R14: INFO_SECTION needs one. */
export const isContent = (type: string): boolean =>
  type === 'TEXT_BLOCK' || type === 'INFO_SECTION';
/** Consents in `consentSectionConfig`; backend rule R13: at least one, each with text and `required`. */
export const isConsent = (type: string): boolean => type === 'CONSENT_SECTION';
/** Fields the user fills in: only these take validators (and so "Wymagane"). */
export const takesValue = (type: string): boolean =>
  isEditableType(type) && !isContent(type) && !isConsent(type);
/**
 * Format validators of the import spec, with their labels. Backend ALLOWED_VALIDATORS: only TEXT_FIELD takes
 * them (other inputs take REQUIRED alone). The editor sets at most one, next to REQUIRED.
 */
export const FORMAT_VALIDATORS = {
  EMAIL: 'Email',
  PESEL: 'PESEL',
  NIP: 'NIP',
  REGON: 'REGON',
  ZIP_CODE: 'Kod pocztowy',
  EPUAP: 'Elektroniczna Skrzynka Podawcza ePUAP',
  ADE: 'Adres do e-Doręczeń',
  SERIAL_NUMBER_ID_CARD: 'Seria i numer dowodu osobistego',
} as const;
export type FormatValidator = keyof typeof FORMAT_VALIDATORS;
const isFormatValidator = (v: string): v is FormatValidator => v in FORMAT_VALIDATORS;
export const takesFormat = (type: string): boolean => type === 'TEXT_FIELD';
/** The field's format validator (the first one, if the JSON had several). */
export const formatOf = (f: FormField): FormatValidator | null =>
  f.validation?.find(isFormatValidator) ?? null;
/** "Pole tylko do odczytu" in the component spec: every input except the file uploader. */
export const takesReadOnly = (type: string): boolean =>
  takesValue(type) && type !== 'FILE_UPLOADER';
/** "Opis" (help text under the label) for inputs; text blocks and info sections use it as their body. */
export const takesDescription = (type: string): boolean => takesValue(type);
/** A fixed default typed in by the author. */
export const takesTextDefault = (type: string): boolean =>
  type === 'TEXT_FIELD' || type === 'TEXTAREA';
/** Types with attributes in the initial data catalog (`GET /initial-data-sources`). */
export const takesInitialData = (type: string): boolean =>
  type === 'TEXT_FIELD' || type === 'DATEPICKER';
export const EXTERNAL_SYSTEM = 'EXTERNAL_SYSTEM';
/** Dynamic states in the spec: sections, inputs and text blocks (not info or consent sections). */
export const takesStates = (f: FormField): boolean =>
  f.type !== 'INFO_SECTION' && f.type !== 'CONSENT_SECTION';
export const STATE_TYPES = { SHOW: 'Pokaż', READ_ONLY: 'Tylko do odczytu' } as const;
export type StateType = keyof typeof STATE_TYPES;
/** Backend rule R11: sections only SHOW. */
export const stateTypesFor = (f: FormField): StateType[] =>
  isSection(f) ? ['SHOW'] : ['SHOW', 'READ_ONLY'];

const TECH_NAME_PATTERN = /^[a-z0-9_]+$/;
/** Same shape as backend slugify output; unique across the form (rule R12). */
export function techNameError(name: string, taken: ReadonlySet<string>): string | null {
  if (!name) return 'Podaj nazwę techniczną.';
  if (!TECH_NAME_PATTERN.test(name))
    return 'Dozwolone są tylko małe litery bez polskich znaków, cyfry i podkreślnik.';
  if (name.length > TECH_NAME_MAX)
    return `Nazwa techniczna może mieć najwyżej ${TECH_NAME_MAX} znaków.`;
  if (taken.has(name)) return 'Ta nazwa techniczna jest już użyta w formularzu.';
  return null;
}
/** Label is optional: the text or the consents themselves say what it is. */
export const titleOptional = (type: string): boolean => isContent(type) || isConsent(type);
/** Backend rule R09: a choice field without a dictionary needs this many options. */
export const minOptions = (type: string): number =>
  type === 'CHECKBOX' ? 1 : isChoice(type) ? 2 : 0;

/** Mirrors ALLOWED_VALIDATORS in backend app/models/form.py: TEXT_FIELD takes all, other inputs only REQUIRED. */
const allowsValidator = (type: string, validator: string): boolean =>
  type === 'TEXT_FIELD' || (takesValue(type) && validator === 'REQUIRED');

const escapeHtml = (text: string): string =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** Plain text → HTML document like the backend writes (html_document + paragraphs); blank lines split paragraphs. */
export function textToHtml(text: string): string {
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`);
  return paragraphs.length ? `<html><head></head><body>${paragraphs.join('')}</body></html>` : '';
}

/** HTML from a converted form → editable plain text (formatting and links are dropped). */
export function htmlToText(html: string | undefined): string {
  if (!html) return '';
  const marked = html.replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|li|div|h[1-6])>/gi, '\n\n');
  const text = new DOMParser().parseFromString(marked, 'text/html').body.textContent ?? '';
  return text
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** One consent; requiredness is set for the whole section (`consentSectionConfig.required`). */
export interface ConsentInput {
  text: string;
}

/** Predefined dictionary chosen for a SELECT (`GET /dictionaries`, status PREDEFINED). */
export interface DictionaryRef {
  name: string;
}

type Consent = NonNullable<FormField['consentSectionConfig']>['consents'][number];

/** Consents whose text did not change keep their original HTML (links, formatting). */
function toConsents(inputs: readonly ConsentInput[], existing: readonly Consent[] = []): Consent[] {
  return inputs.map((c) => {
    const old = existing.find((o) => htmlToText(o.description) === c.text.trim());
    return { ...old, description: old ? old.description : textToHtml(c.text) };
  });
}

/** New consent section in the import document format: one `required` flag and file names. */
const newConsentConfig = (
  consents: Consent[],
  required = true,
  files: readonly string[] = [],
): NonNullable<FormField['consentSectionConfig']> => ({ consents, required, files: [...files] });

function setDictionary(field: FormField, dictionary: DictionaryRef): void {
  // Options come from the dictionary (rule R08); the import format has no other dictionary keys.
  field.dictionaryName = dictionary.name;
  field.options = [];
}

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
  /** Option names, used for choice types only (unless a dictionary is set). */
  options?: readonly string[];
  /** SELECT only: options from this dictionary instead of `options`. */
  dictionary?: DictionaryRef | null;
  /** TEXT_BLOCK and INFO_SECTION: the text shown. */
  content?: string;
  /** CONSENT_SECTION: the consents, whether they are required, and file names to download. */
  consents?: readonly ConsentInput[];
  consentsRequired?: boolean;
  consentFiles?: readonly string[];
  /** TEXT_FIELD only: format validator. */
  format?: FormatValidator | null;
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
    techName: uniqueTechName(def, title || typeLabel(input.type)),
    title,
    description: isContent(input.type) ? textToHtml(input.content ?? '') : '',
    options: isChoice(input.type) ? toOptions(input.options ?? []) : [],
    validation: [
      ...(input.required && takesValue(input.type) ? ['REQUIRED'] : []),
      ...(input.format && takesFormat(input.type) ? [input.format] : []),
    ],
    readOnly: false,
    repeatingSectionGrid: [],
    states: [],
    questionOrder: 0,
    tooltipMessage: '',
  };
  if (input.type === 'SELECT' && input.dictionary) setDictionary(field, input.dictionary);
  if (isConsent(input.type))
    field.consentSectionConfig = newConsentConfig(
      toConsents(input.consents ?? []),
      input.consentsRequired ?? true,
      input.consentFiles,
    );
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
  /** SELECT: a dictionary, or null to go back to own options. */
  dictionary?: DictionaryRef | null;
  /** TEXT_BLOCK, INFO_SECTION: new text. */
  content?: string;
  /** CONSENT_SECTION: the whole list of consents, the section's requiredness, file names. */
  consents?: readonly ConsentInput[];
  consentsRequired?: boolean;
  consentFiles?: readonly string[];
  /** TEXT_FIELD: format validator replacing the current ones, or null to drop them. */
  format?: FormatValidator | null;
  /** "Opis" of an input, plain text ('' clears it). */
  description?: string;
  readOnly?: boolean;
  defaultValue?: DefaultValue;
  /** The whole list of dynamic states. */
  states?: FieldState[];
}

export type DefaultValue =
  | { kind: 'none' }
  /** Fixed text, or the option name of a list (`defaultValue` is a string in the import format). */
  | { kind: 'value'; value: string }
  /** Initial data reference (e.g. `PESEL.name`); not editable attributes force readOnly (rule R10). */
  | { kind: 'initial'; ref: string; editable: boolean };

const CHOICE_ONLY_KEYS = ['dictionaryName'] as const;

/**
 * Changes label, type, requiredness, options, dictionary, text or consents; validators, options and
 * type-specific keys follow what the (new) type allows, so the result stays importable.
 */
export function updateField(def: FormDefinition, id: string, patch: FieldPatch): FormDefinition {
  return updateById(def, id, (f) => {
    const next: FormField & Record<string, unknown> = { ...f };
    if (patch.title !== undefined) next.title = patch.title.trim();
    if (patch.type !== undefined && patch.type !== f.type) {
      next.type = patch.type;
      // A default typed for the old control may not fit the new one.
      delete next.defaultValue;
      delete next.defaultValueType;
      if (!takesReadOnly(patch.type)) next.readOnly = false;
      if (!isChoice(patch.type)) {
        next.options = [];
        for (const key of CHOICE_ONLY_KEYS) delete next[key];
      } else if (patch.type !== 'SELECT' && next.dictionaryName) {
        // Predefined dictionaries are for lists only; the field gets own options below.
        delete next.dictionaryName;
      }
      if (isContent(patch.type) && !isContent(f.type))
        next.description = textToHtml(f.title || typeLabel(patch.type));
      else if (!isContent(patch.type) && isContent(f.type)) next.description = '';
      if (isConsent(patch.type))
        next.consentSectionConfig = newConsentConfig(
          toConsents([{ text: f.title || 'Treść zgody' }]),
        );
      else if (isConsent(f.type)) delete next.consentSectionConfig;
    }
    if (patch.content !== undefined) next.description = textToHtml(patch.content);
    if (patch.description !== undefined) next.description = textToHtml(patch.description);
    if (patch.readOnly !== undefined) next.readOnly = patch.readOnly;
    if (patch.states !== undefined) next.states = patch.states;
    if (patch.defaultValue !== undefined) {
      const dv = patch.defaultValue;
      delete next.defaultValue;
      delete next.defaultValueType;
      if (dv.kind === 'value') next.defaultValue = dv.value;
      else if (dv.kind === 'initial') {
        next.defaultValue = dv.ref;
        next.defaultValueType = EXTERNAL_SYSTEM;
        if (!dv.editable) next.readOnly = true;
      }
    }
    if (isConsent(next.type)) {
      const config = next.consentSectionConfig ?? newConsentConfig([]);
      next.consentSectionConfig = {
        ...config,
        ...(patch.consents && { consents: toConsents(patch.consents, config.consents) }),
        ...(patch.consentsRequired !== undefined && { required: patch.consentsRequired }),
        ...(patch.consentFiles && { files: [...patch.consentFiles] }),
      };
    }
    if (patch.dictionary !== undefined && next.type === 'SELECT') {
      if (patch.dictionary) setDictionary(next, patch.dictionary);
      else delete next.dictionaryName;
    }
    let validation = (f.validation ?? []).filter((v) => allowsValidator(next.type, v));
    if (patch.required !== undefined) {
      validation = validation.filter((v) => v !== 'REQUIRED');
      if (patch.required && allowsValidator(next.type, 'REQUIRED')) validation.unshift('REQUIRED');
    }
    if (patch.format !== undefined && takesFormat(next.type)) {
      validation = validation.filter((v) => !isFormatValidator(v));
      if (patch.format) validation.push(patch.format);
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

/**
 * Moves a field to position `to` (in on-screen order) among its siblings. Fields shift between the existing
 * grid slots and questionOrders, so the layout geometry stays valid. An out-of-range or same position is a no-op.
 */
export function reorderField(def: FormDefinition, id: string, to: number): FormDefinition {
  const moveIn = (qs: Question[]): Question[] => {
    const sorted = sortQuestions(qs);
    const i = sorted.findIndex((q) => q.field.id === id);
    if (i >= 0) {
      if (to === i || to < 0 || to >= sorted.length) return qs;
      const fields = sorted.map((q) => q.field);
      fields.splice(to, 0, ...fields.splice(i, 1));
      const slotOf = new Map(sorted.map((q, k) => [q, k]));
      return qs.map((q) => {
        const f = fields[slotOf.get(q)!];
        return f === q.field ? q : { ...q, field: { ...f, questionOrder: q.field.questionOrder } };
      });
    }
    let changed = false;
    const out = qs.map((q) => {
      const grid = q.field.repeatingSectionGrid;
      const moved = grid?.length ? moveIn(grid) : grid;
      if (moved === grid) return q;
      changed = true;
      return { ...q, field: { ...q.field, repeatingSectionGrid: moved } };
    });
    return changed ? out : qs;
  };
  let changed = false;
  const tabs = def.tabs.map((t) => {
    const questions = moveIn(t.questions);
    if (questions === t.questions) return t;
    changed = true;
    return { ...t, questions };
  });
  return changed ? { ...def, tabs } : def;
}

/** Swaps a field with its neighbour (in on-screen order) among its siblings; past either end is a no-op. */
export function moveField(def: FormDefinition, id: string, offset: -1 | 1): FormDefinition {
  const index = (qs: readonly Question[]): number | null => {
    const i = sortQuestions([...qs]).findIndex((q) => q.field.id === id);
    if (i >= 0) return i;
    for (const q of qs) {
      const r = index(q.field.repeatingSectionGrid ?? []);
      if (r !== null) return r;
    }
    return null;
  };
  for (const t of def.tabs) {
    const i = index(t.questions);
    if (i !== null) return reorderField(def, id, i + offset);
  }
  return def;
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
};
export const typeLabel = (type: string): string =>
  (EDITABLE_TYPES as Record<string, string>)[type] ?? STATIC_TYPE_LABELS[type] ?? type;

/** All techNames in the form (for the uniqueness check, rule R12). */
export const techNames = (def: FormDefinition): Set<string> =>
  new Set(allFields(def).map((f) => f.techName));

/** `'name'` or `"name"` as a whole quoted string (an imported name may hold regex characters). */
const quoted = (name: string, flags = '') =>
  new RegExp(`(['"])${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\1`, flags);

/**
 * Renames a field's techName and the references to it in visibility conditions (`'old' in field.techName`,
 * `'old' in fieldTechName`), so the conditions keep compiling on import (rule R11).
 */
export function renameTechName(def: FormDefinition, id: string, name: string): FormDefinition {
  const old = allFields(def).find((f) => f.id === id)?.techName;
  if (!old || old === name) return def;
  const mentions = quoted(old);
  const every = quoted(old, 'g');
  return mapQuestions(def, (q) => {
    const f = q.field;
    const states = f.states?.some((s) => mentions.test(s.query))
      ? f.states.map((s) => ({ ...s, query: s.query.replace(every, `$1${name}$1`) }))
      : f.states;
    if (f.id !== id && states === f.states) return q;
    return { ...q, field: { ...f, techName: f.id === id ? name : f.techName, states } };
  });
}
