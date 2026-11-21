import { strToU8, zipSync } from 'fflate';

export function resultFileName(name: string): string {
  const dot = name.lastIndexOf('.');
  return `${dot > 0 ? name.slice(0, dot) : name}.json`;
}

export function buildResultsZip(items: { name: string; result: unknown }[]): Blob {
  const used = new Set<string>();
  const entries: Record<string, Uint8Array> = {};
  for (const { name, result } of items) {
    const base = resultFileName(name).slice(0, -'.json'.length);
    let entry = `${base}.json`;
    for (let n = 2; used.has(entry); n++) entry = `${base} (${n}).json`;
    used.add(entry);
    entries[entry] = strToU8(JSON.stringify(result, null, 2));
  }
  return new Blob([zipSync(entries) as BlobPart], { type: 'application/zip' });
}
