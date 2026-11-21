import { Component, computed } from '@angular/core';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-file-uploader-field',
  imports: [FieldLabel],
  template: `
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <app-field-label
      [label]="label()"
      [labelId]="id() + '-label'"
      [hidden]="!hasTitle()"
      [tooltip]="tooltip()"
      [tag]="tag()"
    />
    <div
      class="border rounded-field bg-surface p-section"
      [class]="error() ? 'border-danger' : 'border-border-input'"
      (dragover)="$event.preventDefault()"
      (drop)="$event.preventDefault(); readOnly() || pick($any($event).dataTransfer.files)"
    >
      <div class="flex justify-center">
        <button
          type="button"
          class="border border-primary text-primary rounded-field px-field-x py-field-y font-semibold focus-ring disabled:opacity-60 disabled:cursor-not-allowed"
          [disabled]="readOnly()"
          [attr.aria-describedby]="buttonDescribedBy()"
          [attr.aria-invalid]="error() ? 'true' : null"
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
        (change)="pick($any($event.target).files)"
      />
      @if (value().length) {
        <ul class="mt-2 list-none p-0">
          @for (n of value(); track $index) {
            <li>{{ n }}</li>
          }
        </ul>
      }
      <!-- shortcut: constraints are fixed until the JSON format carries them -->
      <table class="mt-4 w-full text-left text-fg-secondary">
        <tbody class="divide-y divide-border">
          <tr>
            <th scope="row" class="py-1 pr-4 font-normal">Dopuszczalny format pliku:</th>
            <td class="py-1 font-bold">.jpg, .pdf, .png, .jpeg, .doc, .odt, .docx, .ods</td>
          </tr>
          <tr>
            <th scope="row" class="py-1 pr-4 font-normal">Maksymalny rozmiar pliku:</th>
            <td class="py-1 font-bold">10 MB</td>
          </tr>
          <tr>
            <th scope="row" class="py-1 pr-4 font-normal">Maksymalna liczba plików:</th>
            <td class="py-1 font-bold">1</td>
          </tr>
        </tbody>
      </table>
    </div>
    @if (error(); as text) {
      <small [id]="errorId()" class="block text-danger"
        ><span aria-hidden="true">✕</span> {{ text }}</small
      >
    }
  `,
  host: { class: 'block' },
})
export class FileUploaderField extends FieldBase<string[]> {
  protected readonly buttonDescribedBy = computed(() =>
    [this.id() + '-label', this.describedBy()].filter(Boolean).join(' '),
  );
  protected pick(files: FileList | null) {
    if (files?.length) this.set(Array.from(files, (f) => f.name));
  }
}
