import { Component, input, output, signal } from '@angular/core';
import { Button } from '../button/button';

let nextId = 0;

@Component({
  selector: 'app-file-drop',
  imports: [Button],
  template: `
    Przeciągnij pliki tutaj lub
    <button appButton type="button" [attr.aria-describedby]="hintId" (click)="input.click()">
      Wybierz pliki
    </button>
    <small [id]="hintId" class="block text-fg-muted mt-[4px]">
      PDF, DOC, DOCX, ODS, XLSX, JPG, PNG · do {{ maxSizeMb() }} MB · wiele plików naraz
    </small>
    <input
      #input
      type="file"
      multiple
      class="sr-only"
      tabindex="-1"
      aria-hidden="true"
      [accept]="accept()"
      (change)="emit(input.files); input.value = ''"
    />
  `,
  host: {
    class:
      'block border-2 border-dashed border-border-input rounded-card bg-surface p-[18px] text-center text-fg-secondary data-[dragging]:border-primary data-[dragging]:bg-primary-subtle',
    '[attr.data-dragging]': 'dragging() ? "" : null',
    '(dragover)': '$event.preventDefault(); dragging.set(true)',
    '(dragleave)': 'dragging.set(false)',
    '(drop)': '$event.preventDefault(); dragging.set(false); emit($event.dataTransfer?.files)',
  },
})
export class FileDrop {
  readonly accept = input('.pdf,.doc,.docx,.ods,.xlsx,.jpg,.jpeg,.png');
  readonly maxSizeMb = input.required<number>();
  readonly filesSelected = output<File[]>();
  protected readonly dragging = signal(false);
  protected readonly hintId = `app-file-drop-hint-${nextId++}`;

  protected emit(files: FileList | null | undefined) {
    if (files?.length) this.filesSelected.emit(Array.from(files));
  }
}
