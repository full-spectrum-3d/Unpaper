import { Component, forwardRef, input } from '@angular/core';
import { FieldBase } from './field-base';
import { RendererGrid } from '../renderer-grid';

@Component({
  selector: 'app-section-field',
  imports: [forwardRef(() => RendererGrid)],
  template: `
    <section class="bg-surface rounded-card p-section">
      <h4 class="m-0 mb-2 text-title font-bold">{{ field().title }}</h4>
      @if (hasText(field().description)) {
      <div class="text-fg-muted" [innerHTML]="field().description"></div>
    }
      <app-renderer-grid [questions]="field().repeatingSectionGrid ?? []" [hidden]="hidden()" />
    </section>
  `,
  host: { class: 'block' },
})
export class SectionField extends FieldBase {
  readonly hidden = input<ReadonlySet<string>>(new Set());
}
