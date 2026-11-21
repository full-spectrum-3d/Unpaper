import { Component, computed, forwardRef, input } from '@angular/core';
import { FieldHost } from './field-host';
import { Question } from './form-definition';
import { sortQuestions } from './page-order';

@Component({
  selector: 'app-renderer-grid',
  imports: [forwardRef(() => FieldHost)],
  template: `
    @for (q of visible(); track q.field.id) {
      <div [style.grid-area]="area(q)" class="max-sm:[grid-area:auto]!">
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
  protected area = (q: Question) => `${q.y + 1} / ${q.x + 1} / span ${q.rows} / span ${q.cols}`;
}
