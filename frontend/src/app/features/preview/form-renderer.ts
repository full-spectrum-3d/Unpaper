import {
  Component,
  DestroyRef,
  InjectionToken,
  Injector,
  PendingTasks,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
  ElementRef,
} from '@angular/core';
import { Button } from '../../shared/ui/button/button';
import { AnswersStore } from './answers-store';
import { FormDefinition, Question } from './form-definition';
import { orderTabs } from './page-order';
import { RendererGrid } from './renderer-grid';
import { evaluateVisibility } from './visibility';

/** Ids of all fields (nested too) that have a SHOW state: hidden until the first evaluation completes. */
function fieldsWithShow(def: FormDefinition): ReadonlySet<string> {
  const ids = new Set<string>();
  const visit = (qs: Question[]) =>
    qs.forEach(({ field }) => {
      if (field.states?.some((s) => s.type === 'SHOW')) ids.add(field.id);
      visit(field.repeatingSectionGrid ?? []);
    });
  def.tabs.forEach((t) => visit(t.questions));
  return ids;
}

/** Seam so tests can slow down or break the evaluation. */
export const VISIBILITY_EVALUATOR = new InjectionToken<typeof evaluateVisibility>(
  'VISIBILITY_EVALUATOR',
  { factory: () => evaluateVisibility },
);

@Component({
  selector: 'app-form-renderer',
  imports: [RendererGrid, Button],
  providers: [AnswersStore],
  templateUrl: './form-renderer.html',
  host: { class: 'block' },
})
export class FormRenderer {
  readonly definition = input.required<FormDefinition>();

  private readonly store = inject(AnswersStore);
  private readonly injector = inject(Injector);
  private readonly evaluate = inject(VISIBILITY_EVALUATOR);
  private readonly pending = inject(PendingTasks);
  private readonly heading = viewChild<ElementRef<HTMLElement>>('stepHeading');

  protected readonly pages = computed(() => orderTabs(this.definition()));
  protected readonly index = signal(0);
  protected readonly page = computed(() => this.pages()[this.index()]);
  protected readonly isFinish = computed(() => this.page()?.type === 'FINISH');
  protected readonly stepTitle = computed(() => {
    const page = this.page();
    if (!page) return '';
    if (page.type === 'FINISH') return 'Podsumowanie';
    const total = this.pages().filter((p) => p.type !== 'FINISH').length;
    return `Krok ${this.index() + 1} z ${total}: ${page.title}`;
  });

  /** null = not evaluated yet. */
  private readonly evaluated = signal<ReadonlySet<string> | null>(null);
  private readonly initiallyHidden = computed(() => fieldsWithShow(this.definition()));
  protected readonly hidden = computed(() => this.evaluated() ?? this.initiallyHidden());

  private request = 0;

  constructor() {
    // Invalidate in-flight evaluations so none writes after destroy.
    inject(DestroyRef).onDestroy(() => this.request++);
    // Component effects run before this view's template, so fields never see a stale store.
    effect(() => {
      const def = this.definition();
      untracked(() => {
        this.store.init(def);
        this.index.set(0);
        this.evaluated.set(null);
      });
    });

    effect(() => {
      const def = this.definition();
      this.store.version();
      const id = ++this.request;
      const done = this.pending.add();
      queueMicrotask(async () => {
        try {
          // A newer change superseded this request before it started: skip the work.
          if (id !== this.request) return;
          const result = await this.evaluate(def, this.store.snapshot());
          if (id === this.request) this.evaluated.set(result);
        } catch (e) {
          // Fail-open like visibility.ts: better to show every field than to hide them forever.
          console.warn('Visibility evaluation failed', e);
          if (id === this.request) this.evaluated.set(new Set());
        } finally {
          done();
        }
      });
    });
  }

  protected go(index: number) {
    this.index.set(index);
    afterNextRender(
      () => {
        this.heading()?.nativeElement.focus();
        window.scrollTo({ top: 0 });
      },
      { injector: this.injector },
    );
  }

  protected abort() {
    this.store.reset();
    if (this.index() !== 0) this.go(0);
  }
}
