import { Component, ElementRef, Injector, afterNextRender, computed, effect, inject, signal, untracked } from '@angular/core';
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
import { newId } from './new-id';

@Component({
  selector: 'app-import-page',
  imports: [FileDrop, Card, Table, Badge, Progress, Button, RouterLink],
  templateUrl: './import-page.html',
  host: {
    class: 'block p-section',
    '(window:dragover)': 'onWindowDragOver($event)',
    '(window:drop)': '$event.preventDefault()',
    '(window:beforeunload)': 'warnOnUnload($event)',
  },
})
export class ImportPage {
  private readonly store = inject(Store);
  private readonly registry = inject(FileRegistry);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  protected readonly maxSizeMb = MAX_FILE_SIZE_MB;
  protected readonly formatSize = formatSize;
  protected readonly items = this.store.selectSignal(selectQueueItems);
  protected readonly counts = this.store.selectSignal(selectQueueCounts);
  protected readonly doneItems = this.store.selectSignal(selectDoneItems);
  protected readonly summary = computed(() => queueSummary(this.counts()));
  protected readonly announcement = signal('');

  private previous: Map<string, QueueItem['status']> | null = null;
  private announceToggle = false;

  constructor() {
    effect(() => {
      const items = this.items();
      untracked(() => {
        const prev = this.previous;
        this.previous = new Map(items.map((i) => [i.id, i.status]));
        if (!prev) return; // no announcement for the initial render
        const messages: string[] = [];
        for (const i of items) {
          if (prev.get(i.id) === i.status) continue;
          if (i.status === 'done') messages.push(`${i.name}: gotowe`);
          else if (i.status === 'error') messages.push(`${i.name}: błąd – ${i.error}`);
        }
        if (!messages.length) return;
        // Toggling an invisible character makes an identical message change the text, so it is announced again.
        this.announceToggle = !this.announceToggle;
        this.announcement.set(messages.join('. ') + (this.announceToggle ? '\u200B' : ''));
      });
    });
  }

  protected onFiles(files: File[]): void {
    const items: QueueItem[] = files.map((file) => {
      const id = newId();
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
    this.focusAfterRender([`remove-${id}`]);
  }

  protected remove(item: QueueItem): void {
    if (item.status === 'processing') return; // aria-disabled: still focusable, but inert
    const items = this.items();
    const index = items.findIndex((i) => i.id === item.id);
    const neighbours = [items[index + 1], items[index - 1]].filter(Boolean);
    this.store.dispatch(ImportQueueActions.removed({ id: item.id }));
    this.focusAfterRender(neighbours.map((i) => `remove-${i.id}`));
  }

  protected async downloadZip(): Promise<void> {
    const { buildResultsZip } = await import('./zip-results');
    downloadBlob(buildResultsZip(this.doneItems()), 'wyniki-konwersji.zip');
  }

  protected onWindowDragOver(event: DragEvent): void {
    event.preventDefault();
    // Show a "not allowed" cursor anywhere outside the drop zone.
    if (event.dataTransfer && !(event.target instanceof Element && event.target.closest('app-file-drop'))) {
      event.dataTransfer.dropEffect = 'none';
    }
  }

  /** Focuses the first existing element id, else the queue heading (the focused button may have left the DOM). */
  private focusAfterRender(ids: string[]): void {
    afterNextRender(
      () => {
        const root = this.host.nativeElement;
        const target =
          ids.map((id) => root.querySelector<HTMLElement>(`[id="${id}"]`)).find(Boolean) ??
          root.querySelector<HTMLElement>('#queue-title');
        target?.focus();
      },
      { injector: this.injector },
    );
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
