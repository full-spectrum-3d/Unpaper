import { Component, computed, signal } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

// shortcut: constraints are fixed until the JSON format carries them; then read them from the field.
export const FILE_EXTENSIONS = ['.jpg', '.pdf', '.png', '.jpeg', '.doc', '.odt', '.docx', '.ods'];
export const MAX_FILE_MB = 10;

/** Why the file cannot be attached, or null. */
export function fileProblem(file: { name: string; size: number }): string | null {
  const dot = file.name.lastIndexOf('.');
  const ext = dot < 0 ? '' : file.name.slice(dot).toLowerCase();
  if (!FILE_EXTENSIONS.includes(ext)) {
    return `Nie można dodać pliku ${file.name}: niedozwolony format. Dozwolone: ${FILE_EXTENSIONS.join(', ')}`;
  }
  if (file.size > MAX_FILE_MB * 1024 * 1024) {
    return `Nie można dodać pliku ${file.name}: plik jest większy niż ${MAX_FILE_MB} MB`;
  }
  return null;
}

@Component({
  selector: 'app-file-uploader-field',
  imports: [FieldLabel],
  template: `
    <app-field-label
      [label]="label()"
      [labelId]="id() + '-label'"
      [hidden]="!hasTitle()"
      [tooltip]="tooltip()"
      [tag]="tag()"
      [required]="required()"
    />
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <div
      class="border rounded-field bg-surface p-section"
      [class]="error() || fileError() ? 'border-danger' : 'border-border-input'"
      (dragover)="$event.preventDefault()"
      (drop)="$event.preventDefault(); readOnly() || pick($any($event).dataTransfer.files)"
    >
      <div class="flex justify-center">
        <!-- The name starts with the visible text (WCAG 2.5.3) and names the field, so buttons differ. -->
        <button
          type="button"
          class="border border-primary text-primary rounded-field px-field-x py-field-y font-semibold focus-ring disabled:opacity-60 disabled:cursor-not-allowed"
          [disabled]="readOnly()"
          [attr.aria-label]="buttonName()"
          [attr.aria-describedby]="buttonDescribedBy()"
          [attr.aria-invalid]="error() || fileError() ? 'true' : null"
          (click)="input.click()"
        >
          Dodaj lub przeciągnij plik
        </button>
      </div>
      <input
        #input
        type="file"
        class="sr-only"
        tabindex="-1"
        aria-hidden="true"
        [accept]="extensions.join(',')"
        (change)="pick($any($event.target).files); input.value = ''"
      />
      @if (value().length) {
        <ul class="mt-2 list-none p-0">
          @for (n of value(); track $index) {
            <li class="flex items-center gap-2">
              {{ n }}
              @if (!readOnly()) {
                <button
                  type="button"
                  class="p-1 rounded-field text-primary underline focus-ring"
                  [attr.aria-label]="'Usuń plik ' + n"
                  (click)="remove($index)"
                >
                  Usuń
                </button>
              }
            </li>
          }
        </ul>
      }
      <!-- Always in the DOM: live regions inserted with text are not reliably announced. -->
      <p role="status" class="sr-only">{{ notice() }}</p>
      <table class="mt-4 w-full text-left text-fg-secondary">
        <tbody class="divide-y divide-border">
          <tr>
            <th scope="row" class="py-1 pr-4 font-normal">Dopuszczalny format pliku:</th>
            <td class="py-1 font-bold">{{ extensions.join(', ') }}</td>
          </tr>
          <tr>
            <th scope="row" class="py-1 pr-4 font-normal">Maksymalny rozmiar pliku:</th>
            <td class="py-1 font-bold">{{ maxMb }} MB</td>
          </tr>
          <tr>
            <th scope="row" class="py-1 pr-4 font-normal">Maksymalna liczba plików:</th>
            <td class="py-1 font-bold">1</td>
          </tr>
        </tbody>
      </table>
    </div>
    @if (fileError(); as text) {
      <small [id]="fileErrorId()" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
    @if (error(); as text) {
      <small [id]="errorId()" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
  `,
  host: { class: 'block' },
})
export class FileUploaderField extends FieldBase<string[]> {
  protected readonly extensions = FILE_EXTENSIONS;
  protected readonly maxMb = MAX_FILE_MB;
  /** A rejected pick: shown until the next pick or removal. */
  protected readonly fileError = signal<string | null>(null);
  protected readonly notice = signal('');
  protected readonly fileErrorId = computed(() => this.id() + '-file-error');
  protected readonly buttonName = computed(
    () => `Dodaj lub przeciągnij plik: ${this.label()}${this.required() ? ' (wymagane)' : ''}`,
  );
  protected readonly buttonDescribedBy = computed(
    () =>
      [this.describedBy(), this.fileError() && this.fileErrorId()].filter(Boolean).join(' ') ||
      null,
  );

  /** One file at most: the first one dropped or picked replaces the previous. */
  protected pick(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    const problem = fileProblem(file);
    this.fileError.set(problem);
    if (problem) {
      this.notice.set(problem);
      return;
    }
    this.set([file.name]);
    this.notice.set(`Dodano plik ${file.name}`);
  }

  protected remove(index: number) {
    const name = this.value()[index];
    this.set(this.value().filter((_, i) => i !== index));
    this.fileError.set(null);
    this.notice.set(`Usunięto plik ${name}`);
  }
}
