import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { Store } from '@ngrx/store';
import { Subscription } from 'rxjs';
import { toUserMessage } from '../../core/api-error';
import { FormsService } from '../../shared/api/services/forms.service';
import { Button } from '../../shared/ui/button/button';
import { selectQueueItem } from '../../store/import-queue/import-queue.selectors';
import { pluralPl } from '../import/format';
import { formatJson, JsonLines } from '../result/json-lines';
import { JsonView } from '../result/json-view';
import { parseJsonInput, readJsonFile } from './json-input';

interface Issue {
  code: string;
  message: string;
  path?: string;
  linked: boolean;
}
interface CheckResult {
  valid: boolean;
  errors: Issue[];
  warnings: Issue[];
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown): string | undefined => (typeof v === 'string' && v ? v : undefined);

/** Coerces the untyped response; entries that are not objects and non-string fields are dropped. */
function normalize(body: unknown, lines: JsonLines): CheckResult {
  const r = isObject(body) ? body : {};
  const issues = (v: unknown): Issue[] =>
    (Array.isArray(v) ? v : []).filter(isObject).map((o) => {
      const path = str(o['path']);
      return {
        code: str(o['code']) ?? '',
        message: str(o['message']) ?? '',
        path,
        linked: !!path && lines.ranges.has(path),
      };
    });
  return {
    valid: r['valid'] === true,
    errors: issues(r['errors']),
    warnings: issues(r['warnings']),
  };
}

@Component({
  selector: 'app-validator-page',
  imports: [Button, JsonView],
  templateUrl: './validator-page.html',
  host: { class: 'block p-section' },
})
export class ValidatorPage {
  private readonly store = inject(Store);
  private readonly forms = inject(FormsService);
  private readonly injector = inject(Injector);

  readonly item = input<string>();

  protected readonly text = signal('');
  protected readonly checking = signal(false);
  private readonly checkedText = signal<string | null>(null);
  protected readonly checkedLines = signal<JsonLines | null>(null);
  protected readonly result = signal<CheckResult | null>(null);
  protected readonly inputError = signal<string | null>(null);
  protected readonly httpError = signal<string | null>(null);
  protected readonly highlight = signal<string | null>(null);
  protected readonly missingItem = signal(false);

  protected readonly stale = computed(
    () => this.result() !== null && this.text() !== this.checkedText(),
  );
  protected readonly summary = computed(() => {
    const r = this.result();
    if (!r) return '';
    if (r.valid) return 'JSON spełnia reguły COI.';
    const n = r.errors.length;
    const m = r.warnings.length;
    return `Znaleziono ${n} ${pluralPl(n, 'błąd', 'błędy', 'błędów')} i ${m} ${pluralPl(m, 'ostrzeżenie', 'ostrzeżenia', 'ostrzeżeń')}.`;
  });

  private readonly field = viewChild.required<ElementRef<HTMLTextAreaElement>>('field');
  private readonly resultHeading = viewChild<ElementRef<HTMLElement>>('resultHeading');
  private readonly jsonView = viewChild(JsonView);
  private pending?: Subscription;

  constructor() {
    // A late response must not touch a destroyed view (afterNextRender would throw NG0911).
    inject(DestroyRef).onDestroy(() => this.pending?.unsubscribe());
    // Runs on every `item` change only; the queue row is read once, so later store updates never overwrite edits.
    effect(() => {
      const id = this.item();
      if (id === undefined) return;
      untracked(() => {
        const row = this.store.selectSignal(selectQueueItem(id))();
        const found = row?.status === 'done';
        // A newer navigation wins over a request still in flight for the previous item.
        this.pending?.unsubscribe();
        this.checking.set(false);
        this.missingItem.set(!found);
        if (found) {
          this.text.set(JSON.stringify(row.result, null, 2));
          this.check();
        } else {
          this.text.set('');
          this.result.set(null);
          this.checkedText.set(null);
          this.checkedLines.set(null);
          this.httpError.set(null);
          this.inputError.set(null);
        }
      });
    });
  }

  protected onInput(event: Event): void {
    this.text.set((event.target as HTMLTextAreaElement).value);
    this.inputError.set(null);
    this.missingItem.set(false);
  }

  protected async onFile(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ''; // lets the same file be picked again
    if (!file) return;
    const read = await readJsonFile(file);
    if (read.ok) {
      this.text.set(read.text);
      this.inputError.set(null);
    } else {
      this.inputError.set(read.message);
    }
  }

  protected check(): void {
    if (this.checking()) return;
    const text = this.text();
    const parsed = parseJsonInput(text);
    if (!parsed.ok) {
      this.inputError.set(parsed.message);
      this.field().nativeElement.focus();
      return;
    }
    this.inputError.set(null);
    this.checking.set(true);
    this.pending = this.forms.validateApiV1FormsValidatePost({ body: parsed.value }).subscribe({
      next: (body) => {
        const lines = formatJson(parsed.value);
        this.checkedText.set(text);
        this.checkedLines.set(lines);
        this.result.set(normalize(body, lines));
        this.httpError.set(null);
        this.missingItem.set(false);
        this.highlight.set(null);
        this.checking.set(false);
        afterNextRender(() => this.resultHeading()?.nativeElement.focus(), {
          injector: this.injector,
        });
      },
      error: (e: HttpErrorResponse) => {
        this.result.set(null);
        this.checkedText.set(null);
        this.checkedLines.set(null);
        this.httpError.set(
          e.status === 422 ? 'Serwer odrzucił JSON jako niepoprawny.' : toUserMessage(e),
        );
        this.checking.set(false);
      },
    });
  }

  protected showInJson(path: string): void {
    this.highlight.set(path);
    this.jsonView()?.reveal();
  }
}
