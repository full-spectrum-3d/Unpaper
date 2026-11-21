import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import { Badge } from '../../shared/ui/badge/badge';
import { Button } from '../../shared/ui/button/button';
import { Card } from '../../shared/ui/card/card';
import { FileDrop } from '../../shared/ui/file-drop/file-drop';
import { Progress } from '../../shared/ui/progress/progress';
import { Table } from '../../shared/ui/table/table';
import { ImportQueueActions } from '../../store/import-queue/import-queue.actions';
import { QueueItem } from '../../store/import-queue/import-queue.reducer';
import {
  selectDoneItems,
  selectQueueCounts,
  selectQueueItems,
} from '../../store/import-queue/import-queue.selectors';
import { downloadBlob } from './download';
import { FileRegistry } from './file-registry';
import { MAX_FILE_SIZE_MB, validateFile } from './file-validation';
import { formatSize, queueSummary } from './format';
import { buildResultsZip } from './zip-results';

@Component({
  selector: 'app-import-page',
  imports: [FileDrop, Card, Table, Badge, Progress, Button, RouterLink],
  templateUrl: './import-page.html',
  host: {
    class: 'block p-section',
    '(window:dragover)': '$event.preventDefault()',
    '(window:drop)': '$event.preventDefault()',
    '(window:beforeunload)': 'warnOnUnload($event)',
  },
})
export class ImportPage {
  private readonly store = inject(Store);
  private readonly registry = inject(FileRegistry);

  protected readonly maxSizeMb = MAX_FILE_SIZE_MB;
  protected readonly formatSize = formatSize;
  protected readonly items = this.store.selectSignal(selectQueueItems);
  protected readonly counts = this.store.selectSignal(selectQueueCounts);
  protected readonly doneItems = this.store.selectSignal(selectDoneItems);
  protected readonly summary = computed(() => queueSummary(this.counts()));
  protected readonly announcement = signal('');

  private previous: Map<string, QueueItem['status']> | null = null;

  constructor() {
    effect(() => {
      const items = this.items();
      untracked(() => {
        const prev = this.previous;
        this.previous = new Map(items.map((i) => [i.id, i.status]));
        if (!prev) return; // no announcement for the initial render
        for (const i of items) {
          if (prev.get(i.id) === i.status) continue;
          if (i.status === 'done') this.announcement.set(`${i.name}: gotowe`);
          else if (i.status === 'error') this.announcement.set(`${i.name}: błąd – ${i.error}`);
        }
      });
    });
  }

  protected onFiles(files: File[]): void {
    const items: QueueItem[] = files.map((file) => {
      const id = crypto.randomUUID();
      const error = validateFile(file);
      if (!error) this.registry.add(id, file);
      return {
        id,
        name: file.name,
        size: file.size,
        status: error ? 'error' : 'pending',
        error,
        retryable: false,
        result: null,
        startedAt: null,
        durationMs: null,
      };
    });
    this.store.dispatch(ImportQueueActions.filesAdded({ items }));
  }

  protected retry(id: string): void {
    this.store.dispatch(ImportQueueActions.retry({ id }));
  }

  protected remove(id: string): void {
    this.store.dispatch(ImportQueueActions.removed({ id }));
    this.registry.delete(id);
  }

  protected downloadZip(): void {
    downloadBlob(buildResultsZip(this.doneItems()), 'wyniki-konwersji.zip');
  }

  protected seconds(ms: number | null): string {
    return `${Math.round((ms ?? 0) / 1000)} s`;
  }

  protected warnOnUnload(event: BeforeUnloadEvent): void {
    const { processing, pending } = this.counts();
    if (processing + pending > 0) {
      event.preventDefault();
      event.returnValue = true;
    }
  }
}
