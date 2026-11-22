import { Component, computed, input, output } from '@angular/core';
import { Button } from '../../shared/ui/button/button';
import { pluralPl } from '../import/format';
import type { LineRange } from './json-lines';
import { ConversionReport, formatSeconds, pathTarget, ReportIssue } from './report';
import { isObject, num, str } from '../../shared/utils/guards';

const METHODS: Record<string, string> = { pdf_text: 'tekst z PDF', ocr: 'OCR', docx: 'DOCX', xlsx: 'XLSX' };

const STAGES: Record<string, string> = {
  normalizeMs: 'normalizacja',
  extractMs: 'ekstrakcja',
  analyzeMs: 'analiza',
  buildMs: 'budowa',
};

@Component({
  selector: 'app-report-view',
  imports: [Button],
  templateUrl: './report-view.html',
  host: { class: 'block' },
})
export class ReportView {
  readonly report = input.required<ConversionReport | null>();
  readonly ranges = input.required<ReadonlyMap<string, LineRange>>();
  /** JSON path of each field by `techName` (see `fieldPaths`). */
  readonly paths = input<ReadonlyMap<string, string>>(new Map());
  /** Editor row id of each field by `techName`. */
  readonly editIds = input<ReadonlyMap<string, string>>(new Map());
  readonly showInJson = output<string>();
  /** Emits the id of the field to reveal in the editor. */
  readonly showInEditor = output<string>();

  protected readonly pluralPl = pluralPl;
  protected readonly formatSeconds = formatSeconds;

  protected readonly view = computed(() => {
    const r = this.report();
    if (!r) return null;
    const ranges = this.ranges();
    const obj = (v: unknown): Record<string, unknown> => (isObject(v) ? v : {});
    const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
    const editIds = this.editIds();
    const editIdByPath = new Map<string, string>();
    for (const [techName, path] of this.paths()) {
      const id = editIds.get(techName);
      if (id !== undefined) editIdByPath.set(path, id);
    }
    const issues = (v: unknown) =>
      list(v)
        .filter(isObject)
        .map((o) => {
          const issue: ReportIssue = { code: str(o['code']) ?? '', message: str(o['message']) ?? '', path: str(o['path']) };
          return {
            issue,
            target: pathTarget(issue, ranges).kind,
            editId: issue.path === undefined ? undefined : editIdByPath.get(issue.path),
          };
        });
    const stats = obj(r.stats);
    const timings = obj(r.timings);
    const llm = obj(r.llm);
    const file = obj(r.sourceFile);
    const extraction = obj(r.extraction);
    const method = str(extraction['method']);
    const ocr = num(extraction['ocrMeanConfidence']);
    const rows: [string, string][] = [];
    const add = (label: string, value: string | undefined) => value && rows.push([label, value]);
    const pages = num(file['pages']);
    const fileName = str(file['name']);
    add(
      'Plik',
      fileName &&
        fileName +
          (pages ? `, ${pages} ${pluralPl(pages, 'strona', 'strony', 'stron')}` : '') +
          (file['decrypted'] === true ? ', odszyfrowany' : ''),
    );
    add('Ekstrakcja', method && (METHODS[method] ?? method));
    add('Pewność OCR', ocr !== undefined ? `${Math.round(ocr * 100)}%` : undefined);
    const ruleBased = llm['fallback'] === true || llm['ruleBasedDraft'] === true;
    const reason = str(llm['fallbackReason']);
    add('Model LLM', ruleBased ? `szkic regułowy (bez LLM)${reason ? `: ${reason}` : ''}` : str(llm['model']));
    const total = num(r.durationMs);
    const stages = Object.entries(timings).flatMap(([k, v]) => {
      const ms = num(v);
      return ms === undefined ? [] : [`${STAGES[k] ?? k.replace(/Ms$/, '')} ${formatSeconds(ms)}`];
    });
    add('Czas', [...(total === undefined ? [] : [`${formatSeconds(total)} łącznie`]), ...stages].join(' · '));
    const warnings = issues(r.warnings);
    return {
      warnings,
      fixes: issues(r.fixes),
      dictionaries: list(r.dictionaryProposals)
        .filter(isObject)
        .map((d) => ({
          name: str(d['name']) ?? '',
          title: str(d['title']),
          description: str(d['description']),
          count: list(d['items']).length,
          usedBy: list(d['usedBy']).filter((u): u is string => typeof u === 'string'),
        })),
      stats: [
        ['Strony', num(stats['tabs'])],
        ['Sekcje', num(stats['sections'])],
        ['Pola', num(stats['fields'])],
        ['Stany', num(stats['states'])],
      ].filter(([, v]) => v !== undefined),
      rows,
    };
  });
}
