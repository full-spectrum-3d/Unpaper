import { Component, computed, input } from '@angular/core';

export type FileStatus = 'pending' | 'processing' | 'done' | 'error';

const statuses: Record<FileStatus, { label: string; icon: string; classes: string }> = {
  pending: { label: 'Oczekuje', icon: '…', classes: 'bg-warning-subtle text-warning' },
  processing: { label: 'Przetwarzanie', icon: '⟳', classes: 'bg-primary-subtle text-primary' },
  done: { label: 'Gotowe', icon: '✓', classes: 'bg-success-subtle text-success' },
  error: { label: 'Błąd', icon: '✕', classes: 'bg-danger-subtle text-danger' },
};

@Component({
  selector: 'app-badge',
  template: '<span aria-hidden="true">{{ view().icon }}</span>{{ view().label }}',
  host: { '[class]': 'classes()' },
})
export class Badge {
  readonly status = input.required<FileStatus>();
  protected readonly view = computed(() => statuses[this.status()]);
  protected readonly classes = computed(
    () =>
      `inline-flex items-center gap-[5px] rounded-full px-[8px] py-px text-[12px] font-semibold ${this.view().classes}`,
  );
}
