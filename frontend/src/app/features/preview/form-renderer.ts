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
import { FormState } from './form-state';
import { orderTabs } from './page-order';
import { RendererGrid } from './renderer-grid';
import { validateStep } from './validate-step';
import { FieldStates, evaluateStates } from './visibility';

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

/** Identical results must not re-render the grid. */
const sameSet = (a: ReadonlySet<string>, b: ReadonlySet<string>) =>
  a === b || (a.size === b.size && [...a].every((x) => b.has(x)));
const sameStates = (a: FieldStates | null, b: FieldStates | null) =>
  a === b || (!!a && !!b && sameSet(a.hidden, b.hidden) && sameSet(a.readOnly, b.readOnly));
const EMPTY: ReadonlySet<string> = new Set();
const NO_ERRORS: ReadonlyMap<string, string> = new Map();

/** Seam so tests can slow down or break the evaluation. */
export const STATES_EVALUATOR = new InjectionToken<typeof evaluateStates>('STATES_EVALUATOR', {
  factory: () => evaluateStates,
});

@Component({
  selector: 'app-form-renderer',
  imports: [RendererGrid, Button],
  providers: [AnswersStore, FormState],
  templateUrl: './form-renderer.html',
  host: { class: 'block' },
})
export class FormRenderer {
  readonly definition = input.required<FormDefinition>();

  private readonly store = inject(AnswersStore);
  private readonly formState = inject(FormState);
  private readonly injector = inject(Injector);
  private readonly evaluate = inject(STATES_EVALUATOR);
  private readonly pending = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
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
  private readonly evaluated = signal<FieldStates | null>(null, { equal: sameStates });
  private readonly initiallyHidden = computed(() => fieldsWithShow(this.definition()));
  protected readonly hidden = computed(() => this.evaluated()?.hidden ?? this.initiallyHidden());
  readonly readOnlyIds = computed(() => this.evaluated()?.readOnly ?? EMPTY);

  /** Index of the step whose errors are shown (after a failed „Dalej”), or null. */
  private readonly showErrorsFor = signal<number | null>(null);
  private readonly errors = computed(() => {
    if (this.showErrorsFor() !== this.index()) return NO_ERRORS;
    this.store.version();
    return this.validatePage();
  });

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
        this.showErrorsFor.set(null);
      });
    });

    // The only writer of FormState.
    effect(() => {
      this.formState.readOnly.set(this.readOnlyIds());
      this.formState.errors.set(this.errors());
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
          console.warn('State evaluation failed', e);
          if (id === this.request) this.evaluated.set({ hidden: new Set(), readOnly: new Set() });
        } finally {
          done();
        }
      });
    });
  }

  private validatePage() {
    const page = this.page();
    return page
      ? validateStep(page.questions, this.store.snapshot(), this.hidden(), this.readOnlyIds())
      : NO_ERRORS;
  }

  protected next() {
    const errors = this.validatePage();
    if (!errors.size) {
      this.go(this.index() + 1);
      return;
    }
    this.showErrorsFor.set(this.index());
    afterNextRender(
      () => {
        const host = [
          ...this.host.nativeElement.querySelectorAll<HTMLElement>('[data-field-id]'),
        ].find((h) => errors.has(h.dataset['fieldId']!));
        // The invalid control first: a tooltip button may precede it in the label row.
        const control =
          host?.querySelector<HTMLElement>('[aria-invalid="true"]:not([disabled])') ??
          host?.querySelector<HTMLElement>(
            'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])',
          );
        control?.focus();
        control?.scrollIntoView?.({ block: 'center' }); // absent in jsdom
      },
      { injector: this.injector },
    );
  }

  protected go(index: number) {
    this.showErrorsFor.set(null);
    this.index.set(index);
    afterNextRender(
      () => {
        const heading = this.heading()?.nativeElement;
        heading?.focus();
        heading?.scrollIntoView?.({ block: 'start' }); // absent in jsdom
      },
      { injector: this.injector },
    );
  }

  protected abort() {
    this.showErrorsFor.set(null);
    this.store.reset();
    if (this.index() !== 0) this.go(0);
  }
}
