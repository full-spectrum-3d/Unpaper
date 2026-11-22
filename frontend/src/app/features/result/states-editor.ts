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
import jsonata from 'jsonata';
import { Button } from '../../shared/ui/button/button';
import { FieldState } from '../preview/form-definition';
import { STATE_TYPES, StateType } from './form-edit';

/** Why a JSONata condition cannot be saved, or null. */
export function queryError(query: string): string | null {
  if (!query.trim()) return 'Podaj warunek.';
  try {
    jsonata(query);
    return null;
  } catch (e) {
    const message = (e as { message?: string }).message ?? '';
    return `Błąd składni JSONata${message ? `: ${message}` : ''}.`;
  }
}

/**
 * Dynamic states of a field or section: state type (SHOW / READ_ONLY) and a JSONata condition each.
 * Emits the whole list after a change, but only when every condition compiles; the backend also checks
 * that the condition refers to existing pages and fields (rule R11).
 */
@Component({
  selector: 'app-states-editor',
  imports: [Button],
  template: `
    <fieldset class="flex flex-col gap-2">
      <legend class="text-label font-label mb-1">Dynamiczne stany (JSONata)</legend>
      @if (!items().length) {
        <p class="text-fg-muted">Brak warunków — element jest zawsze widoczny.</p>
      }
      @for (s of items(); track $index; let i = $index) {
        <div class="flex flex-col gap-1.5 rounded-field border border-border bg-bg p-2">
          <div class="flex flex-wrap items-end gap-3">
            <div>
              <label [for]="id + '-' + i + '-type'" class="block text-label font-label mb-1"
                >Stan {{ i + 1 }}</label
              >
              <select
                [id]="id + '-' + i + '-type'"
                class="block text-fg text-body border border-border-input rounded-field px-field-x py-field-y bg-surface focus-ring"
                (change)="setType(i, $any($event.target).value)"
              >
                @for (t of types(); track t) {
                  <option [value]="t" [selected]="t === s.type">{{ labels[t] }}</option>
                }
              </select>
            </div>
            <button
              appButton
              type="button"
              variant="ghost"
              class="remove-state ml-auto"
              (click)="removeAt(i)"
            >
              Usuń stan<span class="sr-only"> {{ i + 1 }}</span>
            </button>
          </div>
          <label [for]="id + '-' + i" class="text-label font-label">Warunek {{ i + 1 }}</label>
          <textarea
            [id]="id + '-' + i"
            rows="3"
            spellcheck="false"
            class="block w-full font-mono text-[12px] text-fg border rounded-field px-field-x py-field-y bg-surface focus-ring"
            [class]="errors()[i] ? 'border-danger' : 'border-border-input'"
            [value]="s.query"
            [attr.aria-invalid]="errors()[i] ? 'true' : null"
            [attr.aria-describedby]="errors()[i] ? id + '-' + i + '-error' : null"
            (change)="setQuery(i, $any($event.target).value)"
          ></textarea>
          @if (errors()[i]; as text) {
            <small [id]="id + '-' + i + '-error'" class="block text-danger"
              ><span aria-hidden="true">✕</span> {{ text }}</small
            >
          }
        </div>
      }
      <button appButton type="button" class="add-state self-start" (click)="addOne()">
        <span aria-hidden="true">+</span> Dodaj stan
      </button>
    </fieldset>
  `,
  host: { class: 'block' },
})
export class StatesEditor {
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly value = input.required<readonly FieldState[]>();
  readonly types = input.required<readonly StateType[]>();
  readonly changed = output<FieldState[]>();

  private static nextId = 0;
  protected readonly id = `states-${StatesEditor.nextId++}`;
  protected readonly labels = STATE_TYPES;
  protected readonly items = linkedSignal(() => this.value().map((s) => ({ ...s })));
  /** Shown after the user edits a condition; reset with the saved list. */
  protected readonly errors = linkedSignal<readonly FieldState[], (string | null)[]>({
    source: this.value,
    computation: () => [],
  });

  protected setType(i: number, type: string): void {
    this.items.update((list) => list.map((s, k) => (k === i ? { ...s, type } : s)));
    this.emitIfValid();
  }

  protected setQuery(i: number, query: string): void {
    this.items.update((list) => list.map((s, k) => (k === i ? { ...s, query: query.trim() } : s)));
    this.errors.update((e) => {
      const next = [...e];
      next[i] = queryError(query);
      return next;
    });
    this.emitIfValid();
  }

  protected addOne(): void {
    this.items.update((list) => [...list, { type: this.types()[0], query: '' }]);
    this.focusLater(`#${this.id}-${this.items().length - 1}`);
  }

  protected removeAt(i: number): void {
    this.items.update((list) => list.filter((_, k) => k !== i));
    this.errors.update((e) => e.filter((_, k) => k !== i));
    this.emitIfValid();
    this.focusLater(
      this.items().length
        ? `#${this.id}-${Math.min(i, this.items().length - 1)}`
        : 'button.add-state',
    );
  }

  private emitIfValid(): void {
    if (this.items().every((s) => queryError(s.query) === null)) this.changed.emit(this.items());
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
