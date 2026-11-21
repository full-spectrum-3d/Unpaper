import { Component, computed, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import { Button } from '../../shared/ui/button/button';
import { Card } from '../../shared/ui/card/card';
import { selectQueueItem } from '../../store/import-queue/import-queue.selectors';
import { downloadJson } from '../import/download';
import { resultFileName } from '../import/zip-results';
import { isFormDefinition } from '../preview/form-definition';
import { FormRenderer } from '../preview/form-renderer';

@Component({
  selector: 'app-result-page',
  imports: [Card, Button, RouterLink, FormRenderer],
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
  protected readonly showJson = signal(false);
  protected readonly jsonVisible = computed(() => this.showJson() || !this.form());
  protected readonly json = computed(() => JSON.stringify(this.item()?.result, null, 2));

  protected download(): void {
    const i = this.item();
    if (i) downloadJson(i.result, resultFileName(i.name));
  }
}
