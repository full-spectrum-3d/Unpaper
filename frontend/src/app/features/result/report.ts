import type { LineRange } from './json-lines';

export interface ReportIssue {
  code: string;
  message: string;
  path?: string;
}
export interface ConversionReport {
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

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

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
