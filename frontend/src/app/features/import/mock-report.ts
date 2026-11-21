// Demo conversion report for the mock forms, shaped like the backend `_report()`. Both mocks share the layout below, so the same paths exist in each.
const GRID_FIELD = 'tabs[1].questions[0].field.repeatingSectionGrid[1]';

type Node = { field?: { title?: string; techName?: string; type?: string }; title?: string };

const nodeAt = (form: unknown, path: string): Node | undefined =>
  path
    .match(/[^.[\]]+/g)!
    .reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], form) as Node | undefined;

/** Reads the title at a simple `a[0].b` path so messages name a real element of the form. */
const titleAt = (form: unknown, path: string): string => {
  const node = nodeAt(form, path);
  return node?.field?.title ?? node?.title ?? path;
};

const techAt = (form: unknown, path: string): string => nodeAt(form, path)?.field?.techName ?? 'pole';

/** Path of the first RADIO/SELECT/CHECKBOX field (an array item), found by walking the form. */
const choicePath = (o: unknown, path = ''): string | undefined => {
  if (!o || typeof o !== 'object') return undefined;
  if (path.endsWith(']') && ['RADIO', 'SELECT', 'CHECKBOX'].includes((o as Node).field?.type ?? '')) return path;
  for (const [k, v] of Object.entries(o)) {
    const found = choicePath(v, Array.isArray(o) ? `${path}[${k}]` : path ? `${path}.${k}` : k);
    if (found) return found;
  }
  return undefined;
};

export function mockReport(form: unknown): unknown {
  const choice = choicePath(form)!;
  const gridField = titleAt(form, GRID_FIELD);
  return {
    sourceFile: { name: 'plik-zrodlowy.pdf', sizeBytes: 86016, pages: 4 },
    extraction: { method: 'pdf_text', convertedToOpenXml: false, ocrMeanConfidence: null, blocks: 112 },
    llm: { model: 'claude-sonnet-4-5', fallback: false },
    stats: { tabs: 4, sections: 9, fields: 31, states: 2 },
    dictionaryProposals: [
      {
        name: 'rodzaj_podmiotu',
        title: 'Rodzaj podmiotu',
        description: 'Lista rodzajów podmiotów składających wniosek.',
        itemStructure: ['code', 'label'],
        items: [
          { code: 'OS', label: 'Osoba fizyczna' },
          { code: 'FI', label: 'Firma' },
        ],
        usedBy: [techAt(form, choice)],
      },
    ],
    warnings: [
      {
        code: 'W07_CHOICE_OPTIONS',
        message: `Pole „${titleAt(form, choice)}” ma mniej niż dwie opcje`,
        path: choice,
      },
      { code: 'W02_LABEL_TOO_LONG', message: `Skrócono etykietę pola „${gridField}”`, path: GRID_FIELD },
      {
        code: 'W03_UNPLACED_FIELD',
        message: 'Pole ze szkicu nie trafiło do wyniku',
        path: 'subject_pages[0].sections[0].fields[0]',
      },
    ],
    fixes: [
      {
        code: 'R12_DUPLICATE_TECH_NAME',
        message: `Zmieniono techName na ${techAt(form, GRID_FIELD)}_2`,
        path: GRID_FIELD,
      },
    ],
    timings: { normalizeMs: 410, extractMs: 6230, analyzeMs: 15840, buildMs: 2620 },
    durationMs: 25100,
  };
}
