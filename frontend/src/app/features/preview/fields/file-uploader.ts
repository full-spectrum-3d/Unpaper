import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-file-uploader-field',
  template: `
    <span [id]="id() + '-label'" class="block text-label font-semibold">{{ field().title }}</span>
    @if (hasText(field().description)) {
      <div class="text-fg-muted" [innerHTML]="field().description"></div>
    }
    <div
      class="border border-dashed border-border-input rounded-card bg-surface p-section"
      (dragover)="$event.preventDefault()"
      (drop)="$event.preventDefault(); pick($any($event).dataTransfer.files)"
    >
      <button
        type="button"
        class="border border-primary text-primary rounded-field px-field-x py-field-y font-semibold focus-ring"
        [attr.aria-describedby]="id() + '-label'"
        (click)="input.click()"
      >
        Dodaj lub przeciągnij plik
      </button>
      <input
        #input
        type="file"
        class="sr-only"
        tabindex="-1"
        aria-hidden="true"
        (change)="pick($any($event.target).files)"
      />
      @if (value().length) {
        <ul class="mt-2 list-none p-0">
          @for (n of value(); track $index) {
            <li>{{ n }}</li>
          }
        </ul>
      }
    </div>
    <!-- shortcut: constraints are fixed until the JSON format carries them -->
    <table class="mt-2 text-fg-muted text-left">
      <tbody>
        <tr><th scope="row" class="pr-4 font-semibold">Dopuszczalny format pliku</th><td>.jpg, .pdf, .png, .jpeg, .doc, .odt, .docx, .ods</td></tr>
        <tr><th scope="row" class="pr-4 font-semibold">Maksymalny rozmiar pliku</th><td>10 MB</td></tr>
        <tr><th scope="row" class="pr-4 font-semibold">Maksymalna liczba plików</th><td>1</td></tr>
      </tbody>
    </table>
  `,
  host: { class: 'block' },
})
export class FileUploaderField extends FieldBase<string[]> {
  protected readonly id = computed(() => 'fld-' + this.field().id);
  protected pick(files: FileList | null) {
    if (files?.length) this.set(Array.from(files, (f) => f.name));
  }
}
