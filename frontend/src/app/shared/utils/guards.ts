/** Narrowing helpers for untrusted JSON (API responses, LLM output). */

/** A plain object: not null, not an array. */
export const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/** A non-empty string, else undefined. */
export const str = (v: unknown): string | undefined => (typeof v === 'string' && v ? v : undefined);

/** A finite number, else undefined. */
export const num = (v: unknown): number | undefined =>
  typeof v === 'number' && isFinite(v) ? v : undefined;
