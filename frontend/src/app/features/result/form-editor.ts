import {
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormDefinition, FormField, Question } from '../preview/form-definition';
import { orderTabs, sortQuestions } from '../preview/page-order';
import { Button } from '../../shared/ui/button/button';
import { AddField } from './add-field';
import { FieldRow } from './field-row';
import {
  EditableType,
  FORMAT_VALIDATORS,
  FieldPatch,
  NewField,
  addField,
  isSection,
  moveField,
  removeField,
  renameTechName,
  techNames,
  reorderField,
  typeLabel,
  updateField,
} from './form-edit';

/** Where the pointer holds the drag ghost, from its top-left corner. */
const GRAB_OFFSET = 16;
/** Auto-scroll zone at the window edges while dragging, and the top speed in px per frame. */
const SCROLL_EDGE = 80;
const SCROLL_MAX = 18;

const name = (f: FormField) => `„${f.title || typeLabel(f.type)}”`;

/** Field editor of a converted form: every change is emitted as a whole new definition. */
@Component({
  selector: 'app-form-editor',
  imports: [FieldRow, AddField, Button],
  templateUrl: './form-editor.html',
  styles: `
    .drop-before::before,
    .drop-after::after {
      content: '';
      position: absolute;
      inset-inline: 0;
      height: 4px;
      border-radius: 2px;
      background: var(--color-topbar);
      pointer-events: none;
    }
    .drop-before::before {
      top: -8px;
    }
    .drop-after::after {
      bottom: -8px;
    }
  `,
  host: { class: 'block', '(document:dragover)': 'trackPointer($event)' },
})
export class FormEditor {
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly definition = input.required<FormDefinition>();
  readonly edited = output<FormDefinition>();

  protected readonly pages = computed(() =>
    orderTabs(this.definition()).map((tab) => ({ tab, questions: sortQuestions(tab.questions) })),
  );
  protected readonly status = signal('');
  protected readonly names = computed(() => techNames(this.definition()));
  protected readonly isSection = isSection;
  /** Backend rule W29: the finish page holds only information sections. */
  protected readonly finishTypes: readonly EditableType[] = ['INFO_SECTION'];
  protected readonly children = (q: Question) => sortQuestions(q.field.repeatingSectionGrid ?? []);

  /** Field being dragged and its sibling group (page or section id): drops land only within that group. */
  protected readonly dragged = signal<{ id: string; group: string } | null>(null);
  private readonly dropTarget = signal<{ id: string; after: boolean } | null>(null);
  protected readonly isDropTarget = (f: FormField, after: boolean) => {
    const t = this.dropTarget();
    return t?.id === f.id && t.after === after;
  };

  /** Sections shown as their header only (folded by hand, kept across edits). */
  private readonly foldedIds = signal<ReadonlySet<string>>(new Set());
  protected readonly folded = (f: FormField) => this.foldedIds().has(f.id);
  private readonly sectionIds = computed(() =>
    this.pages().flatMap((p) =>
      p.questions.filter((q) => isSection(q.field)).map((q) => q.field.id),
    ),
  );
  protected readonly allFolded = computed(() =>
    this.sectionIds().every((id) => this.foldedIds().has(id)),
  );
  protected readonly noneFolded = computed(
    () => !this.sectionIds().some((id) => this.foldedIds().has(id)),
  );
  protected readonly hasSections = computed(() => this.sectionIds().length > 0);

  protected toggleFold(field: FormField): void {
    const ids = new Set(this.foldedIds());
    const fold = !ids.delete(field.id);
    if (fold) ids.add(field.id);
    this.foldedIds.set(ids);
  }

  protected foldAll(fold: boolean): void {
    this.foldedIds.set(new Set(fold ? this.sectionIds() : []));
  }
  private pointerY = 0;
  private scrollFrame = 0;

  /** Bubbles up from the handle: the innermost row claims it. */
  protected onDragStart(event: DragEvent, field: FormField, group: string): void {
    event.stopPropagation();
    this.dragged.set({ id: field.id, group });
    this.pointerY = event.clientY;
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', field.title || typeLabel(field.type));
      this.setGhost(event.dataTransfer, field);
    }
    this.autoScroll();
  }

  /** Rows of another group let the event bubble on, so a dragged section finds its own siblings. */
  protected onDragOver(event: DragEvent, field: FormField, group: string): void {
    const d = this.dragged();
    if (!d || d.group !== group) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    if (field.id === d.id) return this.dropTarget.set(null);
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    this.dropTarget.set({ id: field.id, after: event.clientY > rect.top + rect.height / 2 });
  }

  /** The list accepts drops in the gaps between rows too, at the last indicated spot. */
  protected onListDragOver(event: DragEvent, group: string): void {
    if (this.dragged()?.group !== group) return;
    event.preventDefault();
    event.stopPropagation();
  }

  protected onDrop(event: DragEvent, group: string, siblings: Question[]): void {
    const d = this.dragged();
    const target = this.dropTarget();
    if (!d || d.group !== group) return;
    event.preventDefault();
    event.stopPropagation();
    this.onDragEnd();
    if (!target) return;
    const ids = siblings.map((q) => q.field.id);
    const from = ids.indexOf(d.id);
    let to = ids.indexOf(target.id) + (target.after ? 1 : 0);
    if (from < to) to--;
    const field = siblings[from].field;
    const definition = reorderField(this.definition(), d.id, to);
    if (definition === this.definition()) return;
    this.edited.emit(definition);
    this.status.set(`Przesunięto pole ${name(field)} na pozycję ${to + 1} z ${ids.length}.`);
  }

  protected onDragEnd(): void {
    this.dragged.set(null);
    this.dropTarget.set(null);
    cancelAnimationFrame(this.scrollFrame);
  }

  protected trackPointer(event: DragEvent): void {
    if (this.dragged()) this.pointerY = event.clientY;
  }

  /** Scrolls the window near its top or bottom edge, faster the closer the pointer gets. */
  private autoScroll(): void {
    cancelAnimationFrame(this.scrollFrame);
    const step = () => {
      if (!this.dragged()) return;
      const y = this.pointerY;
      const bottom = window.innerHeight - SCROLL_EDGE;
      const speed = y > 0 && y < SCROLL_EDGE ? y - SCROLL_EDGE : y > bottom ? y - bottom : 0;
      if (speed) window.scrollBy(0, (speed / SCROLL_EDGE) * SCROLL_MAX);
      this.scrollFrame = requestAnimationFrame(step);
    };
    this.scrollFrame = requestAnimationFrame(step);
  }

  /** Small label under the pointer instead of a picture of the whole (possibly tall) row. */
  private setGhost(transfer: DataTransfer, field: FormField): void {
    const ghost = document.createElement('div');
    ghost.textContent = `⠿ ${field.title || typeLabel(field.type)}`;
    ghost.style.cssText =
      'position:fixed;top:-1000px;left:0;padding:6px 12px;border-radius:6px;font:600 13px var(--font-sans);' +
      'background:var(--color-topbar);color:var(--color-on-topbar);max-width:320px;white-space:nowrap;' +
      'overflow:hidden;text-overflow:ellipsis;box-shadow:0 4px 12px rgb(0 0 0 / .25)';
    document.body.appendChild(ghost);
    transfer.setDragImage(ghost, 12, GRAB_OFFSET);
    setTimeout(() => ghost.remove());
  }

  protected onPatch(field: FormField, patch: FieldPatch): void {
    const definition = updateField(this.definition(), field.id, patch);
    this.edited.emit(definition);
    if (patch.title !== undefined)
      this.status.set(
        patch.title
          ? `Zmieniono etykietę pola na „${patch.title}”.`
          : `Usunięto tytuł pola ${name(field)}.`,
      );
    else if (patch.optionsFrom !== undefined)
      this.status.set(`Wstawiono do pola ${name(field)} opcje ze słownika „${patch.optionsFrom}”.`);
    else if (patch.dictionary !== undefined)
      this.status.set(
        patch.dictionary
          ? `Pole ${name(field)} bierze teraz opcje ze słownika ${patch.dictionary.name}.`
          : `Pole ${name(field)} ma teraz własne opcje.`,
      );
    else if (patch.content !== undefined) this.status.set(`Zmieniono treść pola ${name(field)}.`);
    else if (patch.consents !== undefined)
      this.status.set(`Zmieniono zgody w polu ${name(field)}.`);
    else if (patch.type !== undefined)
      this.status.set(`Zmieniono typ pola ${name(field)} na ${typeLabel(patch.type)}.`);
    else if (patch.required !== undefined)
      this.status.set(
        `Pole ${name(field)} jest teraz ${patch.required ? 'wymagane' : 'opcjonalne'}.`,
      );
    else if (patch.format !== undefined)
      this.status.set(
        patch.format
          ? `Pole ${name(field)} ma teraz walidator ${FORMAT_VALIDATORS[patch.format]}.`
          : `Usunięto walidator pola ${name(field)}.`,
      );
    else if (patch.description !== undefined)
      this.status.set(`Zmieniono opis pola ${name(field)}.`);
    else if (patch.readOnly !== undefined)
      this.status.set(
        `Pole ${name(field)} ${patch.readOnly ? 'jest teraz tylko do odczytu' : 'można teraz edytować'}.`,
      );
    else if (patch.consentsRequired !== undefined)
      this.status.set(
        `Zgody w polu ${name(field)} są teraz ${patch.consentsRequired ? 'wymagane' : 'opcjonalne'}.`,
      );
    else if (patch.consentFiles !== undefined)
      this.status.set(`Zmieniono pliki zgody w polu ${name(field)}.`);
    else if (patch.defaultValue !== undefined)
      this.status.set(
        patch.defaultValue.kind === 'none'
          ? `Usunięto wartość domyślną pola ${name(field)}.`
          : patch.defaultValue.kind === 'initial'
            ? `Pole ${name(field)} pobiera teraz dane inicjalne ${patch.defaultValue.ref}.`
            : `Zmieniono wartość domyślną pola ${name(field)}.`,
      );
    else if (patch.states !== undefined)
      this.status.set(
        `Zmieniono stany pola ${name(field)} (liczba warunków: ${patch.states.length}).`,
      );
    else this.status.set(`Zmieniono opcje pola ${name(field)}.`);
  }

  protected onRename(field: FormField, techName: string): void {
    const definition = renameTechName(this.definition(), field.id, techName);
    if (definition === this.definition()) return;
    this.edited.emit(definition);
    this.status.set(`Zmieniono nazwę techniczną pola ${name(field)} na ${techName}.`);
  }

  protected onAdd(section: FormField, input: NewField): void {
    const { definition, field } = addField(this.definition(), section.id, input);
    this.edited.emit(definition);
    this.status.set(`Dodano pole ${name(field)}.`);
    this.focusLater(`#edit-field-${field.id} input`);
  }

  /** Keyboard move from the drag handle; focus stays on the moved field's handle. */
  protected onMove(field: FormField, offset: -1 | 1): void {
    const definition = moveField(this.definition(), field.id, offset);
    if (definition === this.definition()) return;
    this.edited.emit(definition);
    this.status.set(`Przesunięto pole ${name(field)} ${offset < 0 ? 'w górę' : 'w dół'}.`);
    this.focusLater(`#edit-field-${field.id} .drag-handle`);
  }

  /** `siblings` in on-screen order; focus goes to the next row, else the previous one, else the parent. */
  protected onRemove(field: FormField, siblings: Question[], parent: FormField | null): void {
    const { definition, droppedStatesOf } = removeField(this.definition(), field.id);
    this.edited.emit(definition);
    const dropped = droppedStatesOf.length
      ? ` Usunięto warunek widoczności: ${droppedStatesOf.map(name).join(', ')}.`
      : '';
    this.status.set(`Usunięto pole ${name(field)}.${dropped}`);
    const i = siblings.findIndex((q) => q.field.id === field.id);
    const next = (siblings[i + 1] ?? siblings[i - 1])?.field ?? parent;
    if (next) this.focusLater(`#edit-field-${next.id} :is(input, select, textarea, button)`);
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
