import {
  Component,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  signal,
  viewChild,
} from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';
import { appTitle } from '../../core/title-strategy';
import { Store } from '@ngrx/store';
import { ImportQueueActions } from '../../store/import-queue/import-queue.actions';
import { Button } from '../../shared/ui/button/button';
import { Card } from '../../shared/ui/card/card';
import { selectQueueItem } from '../../store/import-queue/import-queue.selectors';
import { downloadJson } from '../import/download';
import { resultFileName } from '../import/zip-results';
import { FormDefinition, isFormDefinition } from '../preview/form-definition';
import { FormRenderer } from '../preview/form-renderer';
import { FormEditor } from './form-editor';
import { formatJson } from './json-lines';
import { JsonView } from './json-view';
import { asReport, fieldPaths, formatPercent } from './report';
import { ReportView } from './report-view';
import { ReviewPanel } from './review-panel';

type Tab = 'preview' | 'json' | 'report' | 'edit';
const TAB_LABELS: Record<Tab, string> = {
  preview: 'Podgląd formularza',
  json: 'JSON',
  report: 'Raport',
  edit: 'Edycja',
};

@Component({
  selector: 'app-result-page',
  imports: [Card, Button, RouterLink, FormRenderer, ReportView, ReviewPanel, JsonView, FormEditor],
  templateUrl: './result-page.html',
  host: { class: 'block p-section' },
})
export class ResultPage {
  private readonly store = inject(Store);
  private readonly injector = inject(Injector);
  private readonly title = inject(Title);

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
  protected readonly tabs = computed<Tab[]>(() => (this.form() ? ['preview', 'json', 'report', 'edit'] : ['json', 'report']));
  protected readonly tabLabels = TAB_LABELS;
  // Resets to the default tab when another result is shown (not on edits); no preview tab for a non-form result.
  readonly activeTab = linkedSignal<{ id: string; isForm: boolean }, Tab>({
    source: () => ({ id: this.id(), isForm: !!this.form() }),
    computation: (s, prev) =>
      prev && prev.source.id === s.id && prev.source.isForm === s.isForm
        ? prev.value
        : s.isForm
          ? 'preview'
          : 'json',
  });
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
  private readonly jsonView = viewChild(JsonView);

  constructor() {
    // The route title is just "Wynik"; name the file so tabs and history entries are distinguishable.
    effect(() => {
      const name = this.item()?.name;
      if (name) this.title.setTitle(appTitle(`Wynik: ${name}`));
    });
  }

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
    // The JSON view exists only once the tab has rendered.
    afterNextRender(() => this.jsonView()?.reveal(), { injector: this.injector });
  }

  protected onEdited(result: FormDefinition): void {
    this.store.dispatch(ImportQueueActions.resultEdited({ id: this.id(), result }));
  }

  protected download(): void {
    const i = this.item();
    if (i) downloadJson(i.result, resultFileName(i.name));
  }
}
