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
import { RouterLink } from '@angular/router';
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
import { isObject, str } from '../../shared/utils/guards';

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
  imports: [Button, JsonView, RouterLink],
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
  /** Converted form this check was opened from (?item of a finished queue row): target of the back link. */
  protected readonly sourceItem = signal<string | null>(null);
  /** Persistent live region text, e.g. "Wczytano plik X". */
  protected readonly fileStatus = signal('');

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
  private readonly httpAlert = viewChild<ElementRef<HTMLElement>>('httpAlert');
  private readonly jsonView = viewChild(JsonView);
  private pending?: Subscription;
  /** Bumped by every file pick and navigation: only the latest read may apply its result. */
  private fileRead = 0;

  constructor() {
    // A late response must not touch a destroyed view (afterNextRender would throw NG0911).
    inject(DestroyRef).onDestroy(() => this.pending?.unsubscribe());
    // Runs on every `item` change only; the queue row is read once, so later store updates never overwrite edits.
    // Without an item (also when leaving ?item=X for plain /validator) the page starts empty.
    effect(() => {
      const id = this.item();
      untracked(() => {
        const row = id === undefined ? undefined : this.store.selectSignal(selectQueueItem(id))();
        const found = row?.status === 'done';
        // A newer navigation wins over a request or file read still in flight.
        this.pending?.unsubscribe();
        this.fileRead++;
        this.checking.set(false);
        this.missingItem.set(id !== undefined && !found);
        this.sourceItem.set(found && id !== undefined ? id : null);
        this.text.set(found ? (JSON.stringify(row.result, null, 2) ?? '') : '');
        this.result.set(null);
        this.checkedText.set(null);
        this.checkedLines.set(null);
        this.httpError.set(null);
        this.inputError.set(null);
        this.highlight.set(null);
        if (found) this.check();
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
    const token = ++this.fileRead;
    const read = await readJsonFile(file);
    if (token !== this.fileRead) return; // a later pick or navigation superseded this read
    if (read.ok) {
      this.text.set(read.text);
      this.inputError.set(null);
      this.missingItem.set(false);
      this.fileStatus.set(`Wczytano plik ${file.name}`);
    } else {
      this.inputError.set(read.message);
      this.focusField();
    }
  }

  protected check(): void {
    // aria-disabled keeps the button focusable while checking, so clicks must be ignored here.
    if (this.checking() || !this.text().trim()) return;
    const text = this.text();
    const parsed = parseJsonInput(text);
    if (!parsed.ok) {
      this.inputError.set(parsed.message);
      this.focusField();
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
        afterNextRender(() => this.httpAlert()?.nativeElement.focus(), {
          injector: this.injector,
        });
      },
    });
  }

  /** Focus after render, so the error and aria-describedby exist when the field is announced. */
  private focusField(): void {
    afterNextRender(() => this.field().nativeElement.focus(), { injector: this.injector });
  }

  protected showInJson(path: string): void {
    this.highlight.set(path);
    this.jsonView()?.reveal();
  }
}
