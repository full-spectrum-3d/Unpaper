import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, input, output } from '@angular/core';
import { Button } from '../../shared/ui/button/button';
import { pluralPl } from '../import/format';
import type { LineRange } from './json-lines';
import {
  ConfidenceLevel,
  ConversionReport,
  FieldSource,
  formatPercent,
  ReportField,
  ReviewItem,
} from './report';

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown): string => (typeof v === 'string' ? v : '');
const num = (v: unknown): number | undefined =>
  typeof v === 'number' && isFinite(v) ? v : undefined;
const level = (v: unknown): ConfidenceLevel => (v === 'low' || v === 'medium' ? v : 'high');

const LEVELS: Record<ConfidenceLevel, { label: string; classes: string }> = {
  high: { label: 'wysoka', classes: 'bg-success-subtle text-success' },
  medium: { label: 'średnia', classes: 'bg-warning-subtle text-warning' },
  low: { label: 'niska', classes: 'bg-danger-subtle text-danger' },
};
/** Miniature page width in px; the height follows the page aspect ratio. */
const PAGE_WIDTH = 72;
const A4_ASPECT = 0.707;

interface SourceView {
  page: number;
  text: string;
  /** Position of the block on a miniature page, in px; absent when the format has no fixed pages. */
  mark?: {
    width: number;
    height: number;
    left: number;
    top: number;
    markWidth: number;
    markHeight: number;
  };
}

function sourceView(value: unknown): SourceView | undefined {
  if (!isObject(value)) return undefined;
  const source = value as unknown as FieldSource;
  const page = num(source.page);
  if (page === undefined) return undefined;
  const view: SourceView = { page, text: str(source.text) };
  const box: Record<string, unknown> = isObject(source.box) ? source.box : {};
  const [x, y, w, h] = ['x', 'y', 'width', 'height'].map((k) => num(box[k]));
  if (x !== undefined && y !== undefined && w !== undefined && h !== undefined) {
    const aspect = num(source.pageAspect) || A4_ASPECT;
    const height = Math.round(PAGE_WIDTH / aspect);
    view.mark = {
      width: PAGE_WIDTH,
      height,
      left: Math.round(x * PAGE_WIDTH),
      top: Math.round(y * height),
      // At least a few px, so a single line stays visible on the miniature.
      markWidth: Math.max(4, Math.round(w * PAGE_WIDTH)),
      markHeight: Math.max(3, Math.round(h * height)),
    };
  }
  return view;
}

/** Conversion confidence, the "to review" list and the origin of each document field. */
@Component({
  selector: 'app-review-panel',
  imports: [Button, NgTemplateOutlet],
  templateUrl: './review-panel.html',
  host: { class: 'block' },
})
export class ReviewPanel {
  readonly report = input.required<ConversionReport | null>();
  readonly ranges = input.required<ReadonlyMap<string, LineRange>>();
  /** JSON path of each field by `techName` (see `fieldPaths`). */
  readonly paths = input.required<ReadonlyMap<string, string>>();
  readonly showInJson = output<string>();

  protected readonly levels = LEVELS;
  protected readonly pluralPl = pluralPl;
  protected readonly percent = formatPercent;

  protected readonly view = computed(() => {
    const report = this.report();
    const confidence = isObject(report?.confidence) ? report.confidence : null;
    const score = num(confidence?.['score']);
    if (!report || !confidence || score === undefined) return null;
    const ranges = this.ranges();
    const paths = this.paths();
    const jsonPath = (techName: string): string | undefined => {
      const path = paths.get(techName);
      return path !== undefined && ranges.has(path) ? path : undefined;
    };
    const fields = (Array.isArray(report.fields) ? report.fields : [])
      .filter(isObject)
      .map((raw) => {
        const f = raw as unknown as ReportField;
        return {
          techName: str(f.techName),
          title: str(f.title) || str(f.techName),
          tab: str(f.tab),
          origin: f.origin === 'document' ? ('document' as const) : ('template' as const),
          confidence: num(f.confidence) ?? 0,
          level: level(f.level),
          source: sourceView(f.source),
        };
      });
    const byName = new Map(fields.map((f) => [f.techName, f]));
    const review = (Array.isArray(report.review) ? report.review : [])
      .filter(isObject)
      .map((raw) => {
        const item = raw as unknown as ReviewItem;
        const techName = str(item.techName);
        const field = item.kind === 'field' ? byName.get(techName) : undefined;
        return {
          isField: item.kind === 'field',
          level: level(item.level),
          title: str(item.title),
          tab: str(item.tab),
          messages: (Array.isArray(item.messages) ? item.messages : []).filter(
            (m): m is string => typeof m === 'string',
          ),
          confidence: field?.confidence,
          source: field?.source,
          path: item.kind === 'field' ? jsonPath(techName) : undefined,
        };
      });
    const fromDocument = fields
      .filter((f) => f.origin === 'document')
      .map((f) => ({ ...f, path: jsonPath(f.techName) }));
    return {
      score,
      level: level(confidence['level']),
      total: num(confidence['fieldsTotal']) ?? fields.length,
      fromDocument,
      templates: fields.length - fromDocument.length,
      review,
    };
  });
}
