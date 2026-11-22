import {
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  inject,
  input,
  linkedSignal,
  output,
} from '@angular/core';
import { Button } from '../../shared/ui/button/button';
import { ConsentInput } from './form-edit';

/**
 * List of consents of a CONSENT_SECTION: text, add and remove (at least one stays, rule R13). Requiredness
 * is one flag for the whole section in the import format, so the parent edits it.
 * Emits the whole list after each committed change; an empty text is shown as an error and the parent
 * should not save it.
 */
@Component({
  selector: 'app-consents-editor',
  imports: [Button],
  template: `
    <fieldset class="flex flex-col gap-2">
      <legend class="text-label font-label mb-1.5">Zgody</legend>
      @for (c of items(); track $index; let i = $index) {
        <div class="flex flex-col gap-1.5 rounded-field border border-border bg-bg p-2">
          <label [for]="id + '-' + i" class="text-label font-label"
            >Treść zgody {{ i + 1 }}<span class="text-danger" aria-hidden="true"> *</span></label
          >
          <textarea
            [id]="id + '-' + i"
            rows="2"
            class="block w-full text-fg text-body border rounded-field px-field-x py-field-y bg-surface focus-ring"
            [class]="error(i) ? 'border-danger' : 'border-border-input'"
            aria-required="true"
            [value]="c.text"
            [attr.aria-invalid]="error(i) ? 'true' : null"
            [attr.aria-describedby]="error(i) ? id + '-' + i + '-error' : null"
            (change)="setText(i, $any($event.target).value)"
          ></textarea>
          @if (error(i)) {
            <small [id]="id + '-' + i + '-error'" class="block text-danger"
              ><span aria-hidden="true">✕</span> Podaj treść zgody.</small
            >
          }
          <div class="flex flex-wrap items-center gap-3">
            <button
              appButton
              type="button"
              variant="ghost"
              class="remove-consent ml-auto"
              [disabled]="items().length === 1"
              (click)="removeAt(i)"
            >
              Usuń zgodę<span class="sr-only"> {{ i + 1 }}</span>
            </button>
          </div>
        </div>
      }
      <button appButton type="button" class="add-consent self-start" (click)="addOne()">
        <span aria-hidden="true">+</span> Dodaj zgodę
      </button>
    </fieldset>
  `,
  host: { class: 'block' },
})
export class ConsentsEditor {
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly value = input.required<readonly ConsentInput[]>();
  /** Show errors of all empty texts, not only of the ones the user left empty. */
  readonly showErrors = input(false);
  readonly changed = output<ConsentInput[]>();

  private static nextId = 0;
  protected readonly id = `consents-${ConsentsEditor.nextId++}`;
  /** Resets to the saved list whenever the parent passes a new one. */
  protected readonly items = linkedSignal(() => this.value().map((c) => ({ ...c })));
  private readonly touched = linkedSignal<readonly ConsentInput[], ReadonlySet<number>>({
    source: this.value,
    computation: () => new Set(),
  });
  protected readonly error = (i: number) =>
    (this.showErrors() || this.touched().has(i)) && !this.items()[i]?.text.trim();

  protected setText(i: number, text: string): void {
    this.touched.update((t) => new Set(t).add(i));
    this.update(i, { text: text.trim() });
  }

  protected addOne(): void {
    this.items.update((list) => [...list, { text: '' }]);
    this.focusLater(`#${this.id}-${this.items().length - 1}`);
  }

  protected removeAt(i: number): void {
    this.items.update((list) => list.filter((_, k) => k !== i));
    this.touched.set(new Set());
    this.changed.emit(this.items());
    this.focusLater(`#${this.id}-${Math.min(i, this.items().length - 1)}`);
  }

  private update(i: number, change: Partial<ConsentInput>): void {
    this.items.update((list) => list.map((c, k) => (k === i ? { ...c, ...change } : c)));
    this.changed.emit(this.items());
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
