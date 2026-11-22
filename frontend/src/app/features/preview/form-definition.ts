// Hand-written from wymagania/OpisImportowanegoPlikuJSON.md and wymagania/importowanyPlikJsonSchemat.json
// (their `repetingSectionGrid` is a typo; we use `repeatingSectionGrid`); replace with OpenAPI types once the
// backend exposes them.

export const KNOWN_FIELD_TYPES = [
  'SECTION',
  'REPEATING_SECTION',
  'INFO_SECTION',
  'TEXT_FIELD',
  'NUMBER',
  'TEXTAREA',
  'RADIO',
  'SELECT',
  'CHECKBOX',
  'DATEPICKER',
  'FILE_UPLOADER',
  'TEXT_BLOCK',
  'CONSENT_SECTION',
] as const;

export interface FieldOption {
  id: string;
  name: string;
  techName?: string;
}

export interface FieldState {
  type: string;
  query: string;
}

export interface ConsentSectionConfig {
  consents: { description: string }[];
  /** Requiredness of the consents, set once for the whole section. */
  required?: boolean;
  /** File names offered for download with the consents. */
  files?: string[];
}

export interface FormField {
  id: string;
  /** Unknown types must pass through, so this is not limited to KNOWN_FIELD_TYPES. */
  type: string;
  techName: string;
  title: string;
  description?: string;
  options?: FieldOption[];
  validation?: string[];
  dictionaryName?: string;
  readOnly?: boolean;
  repeatingSectionGrid?: Question[];
  defaultValue?: string;
  defaultValueType?: string;
  consentSectionConfig?: ConsentSectionConfig;
  states?: FieldState[];
  questionOrder?: number;
  tooltipMessage?: string;
}

export interface Question {
  x: number;
  y: number;
  rows: number;
  cols: number;
  field: FormField;
}

export interface FormTab {
  id: string;
  title: string;
  type: 'MAIN' | 'FINISH';
  questions: Question[];
}

export interface FlowLink {
  id?: string;
  source: string;
  target: string;
}

export interface FormDefinition {
  title: string;
  tabs: FormTab[];
  flow: { links: FlowLink[] };
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;

const optionalArrayOf = (v: unknown, item: (x: unknown) => boolean) =>
  v == null || (Array.isArray(v) && v.every(item));
const optionalString = (v: unknown) => v == null || typeof v === 'string';

/** Fields read by the renderer without further checks: a wrong shape here would crash its computeds. */
function isField(f: unknown): boolean {
  return (
    isObject(f) &&
    typeof f['id'] === 'string' &&
    typeof f['type'] === 'string' &&
    optionalString(f['title']) &&
    optionalString(f['techName']) &&
    optionalArrayOf(f['options'], (o) => isObject(o) && typeof o['name'] === 'string') &&
    optionalArrayOf(f['states'], isObject) &&
    optionalArrayOf(f['repeatingSectionGrid'], isQuestion)
  );
}

const isQuestion = (q: unknown): boolean => isObject(q) && isField(q['field']);

/** Recursive shape check of a conversion result (untrusted JSON from the LLM). */
export function isFormDefinition(value: unknown): value is FormDefinition {
  return (
    isObject(value) &&
    typeof value['title'] === 'string' &&
    Array.isArray(value['tabs']) &&
    value['tabs'].every(
      (t) => isObject(t) && Array.isArray(t['questions']) && t['questions'].every(isQuestion),
    )
  );
}
