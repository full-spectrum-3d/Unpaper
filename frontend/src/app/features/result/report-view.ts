import { Component, computed, input, output } from '@angular/core';
import { Button } from '../../shared/ui/button/button';
import { pluralPl } from '../import/format';
import type { LineRange } from './json-lines';
import { ConversionReport, formatSeconds, pathTarget, ReportIssue } from './report';

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
  readonly showInJson = output<string>();

  protected readonly pluralPl = pluralPl;
  protected readonly formatSeconds = formatSeconds;

  protected readonly view = computed(() => {
    const r = this.report();
    if (!r) return null;
    const ranges = this.ranges();
    const withTarget = (list: ReportIssue[] | undefined) =>
      (list ?? []).map((issue) => ({ issue, target: pathTarget(issue, ranges).kind }));
    const stats = r.stats && typeof r.stats === 'object' ? r.stats : {};
    const timings = r.timings && typeof r.timings === 'object' ? r.timings : {};
    const llm = r.llm ?? {};
    return {
      warnings: withTarget(r.warnings),
      fixes: withTarget(r.fixes),
      dictionaries: r.dictionaryProposals ?? [],
      stats: [
        ['Strony', stats.tabs],
        ['Sekcje', stats.sections],
        ['Pola', stats.fields],
        ['Stany', stats.states],
      ].filter(([, v]) => v !== undefined),
      file: r.sourceFile,
      method: r.extraction?.method ? (METHODS[r.extraction.method] ?? r.extraction.method) : null,
      ocr: r.extraction?.ocrMeanConfidence,
      model: llm.model,
      ruleBased: !!(llm.fallback || llm.ruleBasedDraft),
      fallbackReason: llm.fallbackReason,
      total: r.durationMs,
      stages: Object.entries(timings).map(([k, ms]) => [STAGES[k] ?? k.replace(/Ms$/, ''), ms] as const),
    };
  });
}
