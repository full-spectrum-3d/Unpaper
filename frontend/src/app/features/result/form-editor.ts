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
import { AddField } from './add-field';
import { FieldRow } from './field-row';
import {
  FieldPatch,
  NewField,
  addField,
  isSection,
  removeField,
  typeLabel,
  updateField,
} from './form-edit';

const name = (f: FormField) => `„${f.title || typeLabel(f.type)}”`;

/** Field editor of a converted form: every change is emitted as a whole new definition. */
@Component({
  selector: 'app-form-editor',
  imports: [FieldRow, AddField],
  templateUrl: './form-editor.html',
  host: { class: 'block' },
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
  protected readonly isSection = isSection;
  protected readonly children = (q: Question) => sortQuestions(q.field.repeatingSectionGrid ?? []);

  protected onPatch(field: FormField, patch: FieldPatch): void {
    const definition = updateField(this.definition(), field.id, patch);
    this.edited.emit(definition);
    if (patch.title !== undefined) this.status.set(`Zmieniono etykietę pola na „${patch.title}”.`);
    else if (patch.type !== undefined)
      this.status.set(`Zmieniono typ pola ${name(field)} na ${typeLabel(patch.type)}.`);
    else if (patch.required !== undefined)
      this.status.set(
        `Pole ${name(field)} jest teraz ${patch.required ? 'wymagane' : 'opcjonalne'}.`,
      );
    else this.status.set(`Zmieniono opcje pola ${name(field)}.`);
  }

  protected onAdd(section: FormField, input: NewField): void {
    const { definition, field } = addField(this.definition(), section.id, input);
    this.edited.emit(definition);
    this.status.set(`Dodano pole ${name(field)}.`);
    this.focusLater(`#edit-field-${field.id} input`);
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
