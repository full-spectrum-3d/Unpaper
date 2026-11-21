export function foldText(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/ł/g, 'l');
}

/** Substring match ignoring case and diacritics; prefix matches come first (stable). */
export function filterOptions(options: readonly string[], query: string): string[] {
  const q = foldText(query);
  const folded = options.map((o) => [o, foldText(o)] as const).filter(([, f]) => f.includes(q));
  return [
    ...folded.filter(([, f]) => f.startsWith(q)),
    ...folded.filter(([, f]) => !f.startsWith(q)),
  ].map(([o]) => o);
}
