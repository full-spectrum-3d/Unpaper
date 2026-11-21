// Demo conversion report for the mock forms. Both mocks share the shape below, so the same paths exist in each.
const QUESTION = 'tabs[0].questions[1]';
const GRID_FIELD = 'tabs[1].questions[0].field.repeatingSectionGrid[1]';

type Node = { field?: { title?: string }; title?: string };

/** Reads the title at a simple `a[0].b` path so messages name a real element of the form. */
const titleAt = (form: unknown, path: string): string => {
  const node = path
    .match(/[^.[\]]+/g)!
    .reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], form) as Node | undefined;
  return node?.field?.title ?? node?.title ?? path;
};

export function mockReport(form: unknown): unknown {
  const question = titleAt(form, QUESTION);
  const gridField = titleAt(form, GRID_FIELD);
  return {
    sourceFile: { name: 'wniosek.pdf', sizeBytes: 86016, pages: 4 },
    extraction: { method: 'pdf_text', ocrUsed: false, ocrConfidence: null },
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
        usedBy: [QUESTION],
      },
    ],
    warnings: [
      { code: 'W12_LOW_OCR_CONFIDENCE', message: `Niska pewność odczytu pola „${gridField}”`, path: GRID_FIELD },
      { code: 'W07_CHOICE_OPTIONS', message: `Pytanie „${question}” ma mniej niż dwie opcje`, path: QUESTION },
      {
        code: 'W03_UNPLACED_FIELD',
        message: 'Pole ze szkicu nie trafiło do wyniku',
        path: 'subject_pages[0].sections[0].fields[0]',
      },
    ],
    fixes: [
      {
        code: 'R12_DUPLICATE_TECH_NAME',
        message: 'Zmieniono techName na kwota_2',
        path: GRID_FIELD,
      },
    ],
    timings: { normalizeMs: 410, extractMs: 6230, analyzeMs: 15840, buildMs: 2620 },
    durationMs: 25100,
  };
}
