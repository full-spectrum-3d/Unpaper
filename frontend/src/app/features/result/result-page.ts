import {
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  input,
  linkedSignal,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import { Button } from '../../shared/ui/button/button';
import { Card } from '../../shared/ui/card/card';
import { selectQueueItem } from '../../store/import-queue/import-queue.selectors';
import { downloadJson } from '../import/download';
import { resultFileName } from '../import/zip-results';
import { isFormDefinition } from '../preview/form-definition';
import { FormRenderer } from '../preview/form-renderer';
import { formatJson } from './json-lines';
import { asReport, fieldPaths, formatPercent } from './report';
import { ReportView } from './report-view';
import { ReviewPanel } from './review-panel';

type Tab = 'preview' | 'json' | 'report';
const TAB_LABELS: Record<Tab, string> = { preview: 'Podgląd formularza', json: 'JSON', report: 'Raport' };

@Component({
  selector: 'app-result-page',
  imports: [Card, Button, RouterLink, FormRenderer, ReportView, ReviewPanel],
  templateUrl: './result-page.html',
  host: { class: 'block p-section' },
})
export class ResultPage {
  private readonly store = inject(Store);
  private readonly injector = inject(Injector);

  readonly id = input.required<string>();

  // The selector factory runs once per id change, not per template evaluation.
  private readonly select = computed(() => this.store.selectSignal(selectQueueItem(this.id())));
  protected readonly item = computed(() => {
    const i = this.select()();
    return i?.status === 'done' ? i : null;
  });
  protected readonly form = computed(() => {
    const result = this.item()?.result;
    return isFormDefinition(result) ? result : null;
  });
  protected readonly tabs = computed<Tab[]>(() => (this.form() ? ['preview', 'json', 'report'] : ['json', 'report']));
  protected readonly tabLabels = TAB_LABELS;
  // Resets to the default tab when the result changes; no preview tab for a non-form result.
  readonly activeTab = linkedSignal<Tab>(() => (this.form() ? 'preview' : 'json'));
  readonly highlightPath = signal<string | null>(null);
  protected readonly report = computed(() => asReport(this.item()?.report));
  protected readonly json = computed(() => formatJson(this.item()?.result));
  protected readonly fieldPaths = computed(() => fieldPaths(this.item()?.result));
  /** One-line confidence summary above the tabs; null when the report has no confidence. */
  protected readonly summary = computed(() => {
    const confidence = this.report()?.confidence;
    if (typeof confidence?.score !== 'number') return null;
    const toReview = typeof confidence.toReview === 'number' ? confidence.toReview : 0;
    return { score: formatPercent(confidence.score), toReview };
  });
  /** JSON lines split into plain runs and the one highlighted range; newlines kept so textContent stays exact. */
  protected readonly segments = computed(() => {
    const { lines, ranges } = this.json();
    const path = this.highlightPath();
    const range = path === null ? undefined : ranges.get(path);
    const cuts = range ? [0, range.start, range.end + 1, lines.length] : [0, lines.length];
    return cuts.slice(1).map((end, i) => ({
      highlight: !!range && i === 1,
      lines: lines
        .slice(cuts[i], end)
        .map((text, j) => ({ n: cuts[i] + j, text: cuts[i] + j < lines.length - 1 ? text + '\n' : text })),
    }));
  });
  private readonly fragment = viewChild<ElementRef<HTMLElement>>('fragment');

  protected selectTab(tab: Tab): void {
    if (tab !== 'json') this.highlightPath.set(null);
    this.activeTab.set(tab);
  }

  protected onTabKeydown(event: KeyboardEvent): void {
    const tabs = this.tabs();
    const i = tabs.indexOf(this.activeTab());
    const next = { ArrowRight: i + 1, ArrowLeft: i - 1 + tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const tab = tabs[next % tabs.length];
    this.selectTab(tab);
    document.getElementById(`result-tab-${tab}`)?.focus();
  }

  protected onShowInJson(path: string): void {
    this.highlightPath.set(path);
    this.activeTab.set('json');
    afterNextRender(
      () => {
        const el = this.fragment()?.nativeElement;
        // Centre the first line, not the block: a tall range would push its start off-screen.
        el?.querySelector('[data-line]')?.scrollIntoView?.({ block: 'center' });
        el?.focus({ preventScroll: true });
      },
      { injector: this.injector },
    );
  }

  protected download(): void {
    const i = this.item();
    if (i) downloadJson(i.result, resultFileName(i.name));
  }
}
