import type { LineRange } from './json-lines';
import { isObject } from '../../shared/utils/guards';

export interface ReportIssue {
  code: string;
  message: string;
  path?: string;
}
export type ConfidenceLevel = 'high' | 'medium' | 'low';

/** Where a field came from in the source document; `box` is in page fractions (0-1). */
export interface FieldSource {
  page: number;
  text: string;
  blockId?: string;
  box?: { x: number; y: number; width: number; height: number };
  /** Page width divided by height; present together with `box`. */
  pageAspect?: number;
  ocrConfidence?: number;
}
export interface ReportField {
  techName: string;
  title: string;
  tab: string;
  section: string;
  origin: 'document' | 'template';
  confidence: number;
  level: ConfidenceLevel;
  reasons: { code: string; message: string }[];
  source?: FieldSource;
}
export interface ReviewItem {
  kind: 'field' | 'form';
  level: ConfidenceLevel;
  title: string;
  messages: string[];
  techName?: string;
  tab?: string;
  code?: string;
}
export interface ReportConfidence {
  score: number;
  level: ConfidenceLevel;
  fieldsTotal: number;
  fieldsFromDocument: number;
  toReview: number;
}

export interface ConversionReport {
  confidence?: ReportConfidence;
  fields?: ReportField[];
  review?: ReviewItem[];
  sourceFile?: { name?: string; mime?: string; sizeBytes?: number; pages?: number | null; decrypted?: boolean };
  extraction?: { method?: string; convertedToOpenXml?: boolean; ocrMeanConfidence?: number | null; blocks?: number };
  llm?: {
    model?: string | null;
    durationMs?: number;
    retries?: number;
    fallback?: boolean;
    fallbackReason?: string | null;
    ruleBasedDraft?: boolean;
  };
  stats?: { tabs?: number; sections?: number; fields?: number; states?: number };
  dictionaryProposals?: { name: string; title?: string; description?: string; items?: unknown[]; usedBy?: string[] }[];
  warnings?: ReportIssue[];
  fixes?: ReportIssue[];
  timings?: Record<string, number>;
  durationMs?: number;
}

// Never mutates (NgRx state is frozen): returns the input when it is fine, else a shallow copy.
export function asReport(value: unknown): ConversionReport | null {
  if (!isObject(value)) return null;
  const fixed: Record<string, unknown> = {};
  for (const key of ['warnings', 'fixes', 'dictionaryProposals']) {
    if (!Array.isArray(value[key])) fixed[key] = [];
  }
  return (Object.keys(fixed).length ? { ...value, ...fixed } : value) as ConversionReport;
}

export type PathTarget = { kind: 'link' } | { kind: 'draft' } | { kind: 'missing' } | { kind: 'none' };

// First path segment of the draft (FormDraft), as opposed to the result form.
const DRAFT_PREFIX = /^(subject_pages|chunk|title|authority_name|attachments)(?![\w])/;

export function pathTarget(issue: ReportIssue, ranges: ReadonlyMap<string, LineRange>): PathTarget {
  const { path, code } = issue;
  if (typeof path !== 'string' || !path) return { kind: 'none' };
  if (DRAFT_PREFIX.test(path)) return { kind: 'draft' };
  if (!path.startsWith('tabs[')) return { kind: 'missing' };
  return ranges.has(path) && code !== 'R03_EMPTY_PAGE' ? { kind: 'link' } : { kind: 'missing' };
}

export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1).replace('.', ',')} s`;
}

type FormNode = { field?: { techName?: unknown; repeatingSectionGrid?: unknown } };

/**
 * JSON path of every field by `techName`, in the syntax of `formatJson` ranges.
 * Nested `repeatingSectionGrid`s are followed to any depth; a duplicated techName keeps its first path.
 */
export function fieldPaths(form: unknown): ReadonlyMap<string, string> {
  const paths = new Map<string, string>();
  const walk = (nodes: unknown, base: (k: number) => string): void => {
    (Array.isArray(nodes) ? (nodes as FormNode[]) : []).forEach((node, k) => {
      const path = base(k);
      const name = node?.field?.techName;
      if (typeof name === 'string' && !paths.has(name)) paths.set(name, path);
      walk(node?.field?.repeatingSectionGrid, (n) => `${path}.field.repeatingSectionGrid[${n}]`);
    });
  };
  const tabs = isObject(form) && Array.isArray(form['tabs']) ? form['tabs'] : [];
  tabs.forEach((tab, i) => walk(isObject(tab) ? tab['questions'] : [], (j) => `tabs[${i}].questions[${j}]`));
  return paths;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
