import { Component } from '@angular/core';
import { FieldBase } from './field-base';

@Component({
  selector: 'app-file-uploader-field',
  template: `
    @if (hasDescription()) {
      <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
    }
    <span [id]="id() + '-label'" [class]="labelClass()">{{ label() }}</span>
    <div
      class="border border-border-input rounded-field bg-surface p-section"
      (dragover)="$event.preventDefault()"
      (drop)="$event.preventDefault(); pick($any($event).dataTransfer.files)"
    >
      <div class="flex justify-center">
        <button
          type="button"
          class="border border-primary text-primary rounded-field px-field-x py-field-y font-semibold focus-ring"
          [attr.aria-describedby]="id() + '-label'"
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
  `,
  host: { class: 'block' },
})
export class FileUploaderField extends FieldBase<string[]> {
  protected pick(files: FileList | null) {
    if (files?.length) this.set(Array.from(files, (f) => f.name));
  }
}
