export interface LineRange {
  start: number; // 0-based, inclusive
  end: number;
}

export interface JsonLines {
  lines: string[];
  ranges: ReadonlyMap<string, LineRange>;
}

const isSkipped = (v: unknown): boolean => v === undefined || typeof v === 'function' || typeof v === 'symbol';

/**
 * Pretty-prints like `JSON.stringify(value, null, 2)` and maps each object/array value
 * (and each primitive) to its line range. Path syntax matches the backend: `a.b[0].c`, no leading dot.
 * shortcut: keys containing dots or brackets are concatenated without escaping, so paths
 * can collide; upgrade if the backend ever escapes them. `toJSON` is not honoured (plain JSON only).
 */
export function formatJson(value: unknown): JsonLines {
  const lines: string[] = [];
  const ranges = new Map<string, LineRange>();

  // `lead` is the text before the value on its first line (indent + key).
  const write = (v: unknown, depth: number, path: string, lead: string): void => {
    if (typeof v !== 'object' || v === null) {
      lines.push(lead + (JSON.stringify(v) ?? 'null'));
      // Primitives are mapped too (brief requires `title` -> one line); superset of the spec.
      ranges.set(path, { start: lines.length - 1, end: lines.length - 1 });
      return;
    }
    const isArray = Array.isArray(v);
    const [open, close] = isArray ? ['[', ']'] : ['{', '}'];
    const entries: [string, unknown][] = isArray
      ? v.map((item, i): [string, unknown] => [String(i), item])
      : Object.entries(v).filter(([, x]) => !isSkipped(x));
    const start = lines.length;
    if (entries.length === 0) {
      lines.push(lead + open + close);
    } else {
      lines.push(lead + open);
      const pad = '  '.repeat(depth + 1);
      entries.forEach(([k, item], i) => {
        const childPath = isArray ? `${path}[${k}]` : path ? `${path}.${k}` : k;
        const childLead = isArray ? pad : `${pad}${JSON.stringify(k)}: `;
        write(isArray && isSkipped(item) ? null : item, depth + 1, childPath, childLead);
        if (i < entries.length - 1) lines[lines.length - 1] += ',';
      });
      lines.push('  '.repeat(depth) + close);
    }
    ranges.set(path, { start, end: lines.length - 1 });
  };

  write(value, 0, '', '');
  return { lines, ranges };
}
