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
import { Progress } from '../../shared/ui/progress/progress';
import { AnswersStore } from './answers-store';
import { FormDefinition, FormTab, Question } from './form-definition';
import { FormState } from './form-state';
import { orderTabs, sortQuestions } from './page-order';
import { findDictionary } from './sample-dictionaries';
import { RendererGrid } from './renderer-grid';
import { validateStep } from './validate-step';
import { FieldStates, evaluateStates } from './visibility';

/** Containers and static content: no answer of their own in the summary. */
const NOT_ANSWERS = new Set([
  'SECTION',
  'REPEATING_SECTION',
  'INFO_SECTION',
  'TEXT_BLOCK',
  'CONSENT_SECTION',
]);
const display = (v: unknown): string => {
  const text = Array.isArray(v) ? v.filter(Boolean).join(', ') : typeof v === 'string' ? v : '';
  return text.trim() || '—';
};

const isBlank = (v: unknown) =>
  v == null || (typeof v === 'string' && !v.trim()) || (Array.isArray(v) && !v.length);

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

/** Typing pauses this long before the jsonata states are re-evaluated (each run clones the definition). */
const EVALUATION_DEBOUNCE_MS = 150;

/** Whether any field (nested too) carries REQUIRED: only then the asterisk legend is shown. */
function hasRequired(qs: Question[]): boolean {
  return qs.some(
    ({ field }) =>
      (Array.isArray(field.validation) && field.validation.includes('REQUIRED')) ||
      hasRequired(field.repeatingSectionGrid ?? []),
  );
}

/** Seam so tests can slow down or break the evaluation. */
export const STATES_EVALUATOR = new InjectionToken<typeof evaluateStates>('STATES_EVALUATOR', {
  factory: () => evaluateStates,
});

@Component({
  selector: 'app-form-renderer',
  imports: [RendererGrid, Button, Progress],
  providers: [AnswersStore, FormState],
  templateUrl: './form-renderer.html',
  host: { class: 'block', '(focusout)': 'onFocusOut($event)' },
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
  private readonly abortButton = viewChild<ElementRef<HTMLElement>>('abortButton');
  private readonly cancelAbortButton = viewChild('cancelAbortButton', {
    read: ElementRef<HTMLElement>,
  });

  protected readonly pages = computed(() => orderTabs(this.definition()));
  /** Pages of the definition the store was last initialised with, to find the step again after an edit. */
  private shownPages: FormTab[] = [];
  protected readonly index = signal(0);
  protected readonly page = computed(() => this.pages()[this.index()]);
  protected readonly isFinish = computed(() => this.page()?.type === 'FINISH');
  protected readonly pageHasRequired = computed(() => hasRequired(this.page()?.questions ?? []));
  /** „Przerwij wypełnianie” asks first: it wipes every answer. */
  protected readonly confirmingAbort = signal(false);
  /** Persistent live region text (inserted regions are not reliably announced). */
  protected readonly announcement = signal('');
  /** On the FINISH page: the visible answers of every earlier page, label and value. */
  protected readonly summary = computed(() => {
    if (!this.isFinish()) return [];
    this.store.version();
    const answers = this.store.snapshot();
    const hidden = this.hidden();
    return this.pages()
      .filter((p) => p.type !== 'FINISH')
      .map((p) => {
        const rows: { id: string; label: string; value: string }[] = [];
        // Same order as on screen: rows top-down, then columns.
        const visit = (qs: Question[]) =>
          sortQuestions(qs).forEach(({ field }) => {
            if (hidden.has(field.id)) return;
            if (!NOT_ANSWERS.has(field.type)) {
              // TERYT carries the dictionary name as its title: label it by its levels, as on screen.
              const levels = findDictionary(field.dictionaryName)?.levels.join(', ');
              const titled = field.title && field.title !== field.dictionaryName;
              const label = (titled ? field.title : levels) || field.title || field.techName;
              rows.push({ id: field.id, label, value: display(answers.get(field.id)) });
            }
            visit(field.repeatingSectionGrid ?? []);
          });
        visit(p.questions);
        return { id: p.id, title: p.title, rows };
      })
      .filter((p) => p.rows.length);
  });
  private readonly stepCount = computed(
    () => this.pages().filter((p) => p.type !== 'FINISH').length,
  );
  /** Share of the form reached, counting the current step; 100 on the summary. */
  protected readonly progress = computed(() =>
    this.isFinish() ? 100 : ((this.index() + 1) / Math.max(1, this.stepCount())) * 100,
  );
  protected readonly progressText = computed(() =>
    this.isFinish() ? 'Podsumowanie' : `Krok ${this.index() + 1} z ${this.stepCount()}`,
  );
  protected readonly stepTitle = computed(() => {
    const page = this.page();
    if (!page) return '';
    if (page.type === 'FINISH') return 'Podsumowanie';
    return `Krok ${this.index() + 1} z ${this.stepCount()}: ${page.title}`;
  });

  /** null = not evaluated yet. */
  private readonly evaluated = signal<FieldStates | null>(null, { equal: sameStates });
  private readonly initiallyHidden = computed(() => fieldsWithShow(this.definition()));
  protected readonly hidden = computed(() => this.evaluated()?.hidden ?? this.initiallyHidden());
  readonly readOnlyIds = computed(() => this.evaluated()?.readOnly ?? EMPTY);

  /** Index of the step whose errors are shown (after a failed „Dalej”), or null. */
  private readonly showErrorsFor = signal<number | null>(null);
  /** Fields the user has left on this step: their format errors show before „Dalej”. */
  private readonly touched = signal<ReadonlySet<string>>(new Set());
  private readonly errors = computed(() => {
    const submitted = this.showErrorsFor() === this.index();
    const touched = this.touched();
    if (!submitted && !touched.size) return NO_ERRORS;
    this.store.version();
    const errors = this.validatePage();
    if (submitted) return errors;
    // Leaving an empty field is not an error yet: REQUIRED waits for „Dalej”.
    const answers = this.store.snapshot();
    return new Map([...errors].filter(([id]) => touched.has(id) && !isBlank(answers.get(id))));
  });

  private request = 0;
  private debounce?: ReturnType<typeof setTimeout>;
  /** One pending task spans the debounce and the evaluation, so whenStable waits for the result. */
  private pendingDone?: () => void;

  constructor() {
    // Invalidate in-flight evaluations so none writes after destroy.
    inject(DestroyRef).onDestroy(() => {
      this.request++;
      clearTimeout(this.debounce);
      this.settle();
    });
    // Component effects run before this view's template, so fields never see a stale store.
    effect(() => {
      const def = this.definition();
      untracked(() => {
        // An edited form keeps the answers, the current step and touched fields that still exist.
        const pageId = this.shownPages[this.index()]?.id;
        this.store.init(def);
        const ids = new Set(this.store.snapshot().keys());
        this.shownPages = orderTabs(def);
        this.index.set(
          Math.max(
            0,
            this.shownPages.findIndex((t) => t.id === pageId),
          ),
        );
        this.evaluated.set(null);
        this.showErrorsFor.set(null);
        this.touched.update((t) => new Set([...t].filter((id) => ids.has(id))));
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
      this.pendingDone ??= this.pending.add();
      clearTimeout(this.debounce);
      // The first evaluation runs at once: fields with SHOW stay hidden until it completes.
      const delay = untracked(this.evaluated) === null ? 0 : EVALUATION_DEBOUNCE_MS;
      this.debounce = setTimeout(async () => {
        try {
          const result = await this.evaluate(def, this.store.snapshot());
          if (id === this.request) this.evaluated.set(result);
        } catch (e) {
          // Fail-open like visibility.ts: better to show every field than to hide them forever.
          console.warn('State evaluation failed', e);
          if (id === this.request) this.evaluated.set({ hidden: new Set(), readOnly: new Set() });
        } finally {
          // A superseded evaluation leaves the task to the newer one.
          if (id === this.request) this.settle();
        }
      }, delay);
    });
  }

  private settle() {
    this.pendingDone?.();
    this.pendingDone = undefined;
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

  protected onFocusOut(event: FocusEvent) {
    const id = (event.target as Element | null)?.closest<HTMLElement>('[data-field-id]')?.dataset[
      'fieldId'
    ];
    if (id && !this.touched().has(id)) this.touched.update((t) => new Set(t).add(id));
  }

  protected go(index: number) {
    this.showErrorsFor.set(null);
    this.touched.set(new Set());
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

  protected askAbort() {
    this.announcement.set('');
    this.confirmingAbort.set(true);
    // The safe choice gets focus: Enter right after the click must not wipe the answers.
    this.focusAfterRender(() => this.cancelAbortButton());
  }

  protected cancelAbort() {
    this.confirmingAbort.set(false);
    this.focusAfterRender(() => this.abortButton());
  }

  protected abort() {
    this.confirmingAbort.set(false);
    this.showErrorsFor.set(null);
    this.touched.set(new Set());
    this.store.reset();
    this.announcement.set('Wyczyszczono odpowiedzi');
    if (this.index() !== 0) this.go(0);
    else this.focusAfterRender(() => this.abortButton());
  }

  private focusAfterRender(target: () => ElementRef<HTMLElement> | undefined) {
    afterNextRender(() => target()?.nativeElement.focus(), { injector: this.injector });
  }
}
