// Hand-written from wymagania/importowanyPlikJsonSchemat.json; replace with OpenAPI types once the backend exposes them.

export const KNOWN_FIELD_TYPES = [
  'SECTION',
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
  consents: { description: string; required?: boolean }[];
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
  defaultValue?: string | string[];
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

/** Shallow shape check of a conversion result. */
export function isFormDefinition(value: unknown): value is FormDefinition {
  return (
    isObject(value) &&
    typeof value['title'] === 'string' &&
    Array.isArray(value['tabs']) &&
    value['tabs'].every((t) => isObject(t) && Array.isArray(t['questions']))
  );
}
