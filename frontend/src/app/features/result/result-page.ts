import {
  Component,
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
import { JsonView } from './json-view';
import { asReport } from './report';
import { ReportView } from './report-view';

type Tab = 'preview' | 'json' | 'report';
const TAB_LABELS: Record<Tab, string> = { preview: 'Podgląd formularza', json: 'JSON', report: 'Raport' };

@Component({
  selector: 'app-result-page',
  imports: [Card, Button, RouterLink, FormRenderer, ReportView, JsonView],
  templateUrl: './result-page.html',
  host: { class: 'block p-section' },
})
export class ResultPage {
  private readonly store = inject(Store);

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
  private readonly jsonView = viewChild.required(JsonView);

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
    this.jsonView().reveal();
  }

  protected download(): void {
    const i = this.item();
    if (i) downloadJson(i.result, resultFileName(i.name));
  }
}
