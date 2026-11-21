import { Component, computed, forwardRef, input } from '@angular/core';
import { FieldHost } from './field-host';
import { Question } from './form-definition';
import { sortQuestions } from './page-order';

/** Grid row per question, numbered from the visible questions only so hidden rows leave no gap. */
export function gridRows(visible: Question[]): Map<Question, number> {
  const ys = [...new Set(visible.map((q) => q.y))].sort((a, b) => a - b);
  return new Map(visible.map((q) => [q, ys.indexOf(q.y) + 1]));
}

@Component({
  selector: 'app-renderer-grid',
  imports: [forwardRef(() => FieldHost)],
  template: `
    @for (q of visible(); track q.field.id) {
      <div
        [style.grid-row]="rows().get(q) + ' / span 1'"
        [style.grid-column]="q.x + 1 + ' / span ' + q.cols"
        class="max-sm:[grid-area:auto]!"
      >
        <app-field-host [field]="q.field" [hidden]="hidden()" />
      </div>
    }
  `,
  host: { class: 'grid grid-cols-3 max-sm:grid-cols-1 gap-4' },
})
export class RendererGrid {
  readonly questions = input.required<Question[]>();
  readonly hidden = input<ReadonlySet<string>>(new Set());
  protected readonly visible = computed(() =>
    sortQuestions(this.questions()).filter((q) => !this.hidden().has(q.field.id)),
  );
  protected readonly rows = computed(() => gridRows(this.visible()));
}
