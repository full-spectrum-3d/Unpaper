export type ParseResult =
  { ok: true; value: Record<string, unknown> } | { ok: false; message: string };

export const MAX_JSON_FILE_BYTES = 5 * 1024 * 1024;

const NOT_OBJECT = 'JSON musi być obiektem formularza (zaczynać się od {).';
const BAD_FILE = 'Wgraj plik .json do 5 MB.';
// V8 shows at most this many characters before the error position in its snippet.
const V8_CONTEXT = 10;

export function positionToLineColumn(text: string, pos: number): { line: number; column: number } {
  const before = text.slice(0, pos);
  return {
    line: before.split('\n').length,
    column: pos - before.lastIndexOf('\n'),
  };
}

export function extractPosition(message: string, text: string): number | null {
  const at = /at position (\d+)/.exec(message);
  if (at) return Number(at[1]);

  const lc = /line (\d+) column (\d+)/.exec(message);
  if (lc) {
    const lines = text.split('\n');
    const line = Number(lc[1]);
    if (line > lines.length) return null;
    const offset = lines.slice(0, line - 1).reduce((sum, l) => sum + l.length + 1, 0);
    return offset + Math.min(Number(lc[2]) - 1, lines[line - 1].length);
  }

  // Node prints only a snippet of the source; V8 shows [pos-10, pos+10) around the error.
  // Every branch returns null unless the position is unambiguous: a wrong location is worse than none.
  const snip = /^Unexpected token '(.)', (\.\.\.)?"([\s\S]*?)"(\.\.\.)? is not valid JSON$/.exec(
    message,
  );
  if (!snip) return null;
  const [, token, head, snippet, tail] = snip;
  let pos: number;
  if (head) {
    const start = text.indexOf(snippet);
    if (start < 0 || start !== text.lastIndexOf(snippet)) return null;
    pos = start + V8_CONTEXT;
  } else if (tail) {
    if (!text.startsWith(snippet)) return null;
    pos = snippet.length - V8_CONTEXT;
  } else {
    if (snippet !== text || snippet.indexOf(token) !== snippet.lastIndexOf(token)) return null;
    pos = snippet.indexOf(token);
  }
  return text[pos] === token ? pos : null;
}

export function parseJsonInput(text: string): ParseResult {
  // Only the BOM is removed: leading whitespace stays so reported lines match what the user sees.
  const source = text.replace(/^﻿/, '');
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch (e) {
    const pos = extractPosition(e instanceof Error ? e.message : '', source);
    if (pos === null) return { ok: false, message: 'Niepoprawny JSON.' };
    const { line, column } = positionToLineColumn(source, pos);
    return { ok: false, message: `Niepoprawny JSON: linia ${line}, kolumna ${column}.` };
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return { ok: false, message: NOT_OBJECT };
  }
  return { ok: true, value: value as Record<string, unknown> };
}

export async function readJsonFile(
  file: File,
): Promise<{ ok: true; text: string } | { ok: false; message: string }> {
  if (!/\.json$/i.test(file.name) || file.size > MAX_JSON_FILE_BYTES) {
    return { ok: false, message: BAD_FILE };
  }
  return { ok: true, text: await file.text() };
}
