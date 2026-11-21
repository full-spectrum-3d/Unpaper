import { Component, InjectionToken, forwardRef, inject, input } from '@angular/core';
import { FieldBase } from './field-base';
import { RendererGrid } from '../renderer-grid';

/** Heading level of the nearest enclosing section; the step heading above top-level sections is h3. */
const SECTION_LEVEL = new InjectionToken<number>('SECTION_LEVEL');

@Component({
  selector: 'app-section-field',
  imports: [forwardRef(() => RendererGrid)],
  template: `
    <section class="bg-surface rounded-card p-section">
      @switch (level) {
        @case (4) {
          <h4 class="m-0 mb-2 text-section-title font-bold">{{ label() }}</h4>
        }
        @case (5) {
          <h5 class="m-0 mb-2 text-section-title font-bold">{{ label() }}</h5>
        }
        @default {
          <h6 class="m-0 mb-2 text-section-title font-bold">{{ label() }}</h6>
        }
      }
      @if (hasDescription()) {
        <div class="text-fg-muted mb-2" [id]="descId()" [innerHTML]="field().description"></div>
      }
      <app-renderer-grid [questions]="field().repeatingSectionGrid ?? []" [hidden]="hidden()" />
    </section>
  `,
  host: { class: 'block' },
  providers: [
    {
      provide: SECTION_LEVEL,
      // HTML has no h7: deeper sections stay at h6.
      useFactory: () =>
        Math.min((inject(SECTION_LEVEL, { skipSelf: true, optional: true }) ?? 3) + 1, 6),
    },
  ],
})
export class SectionField extends FieldBase {
  protected readonly level = inject(SECTION_LEVEL);
  readonly hidden = input<ReadonlySet<string>>(new Set());
}
