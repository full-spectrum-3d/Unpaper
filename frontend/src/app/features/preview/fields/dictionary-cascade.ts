import { Component, computed } from '@angular/core';
import { Combobox } from '../../../shared/ui/combobox/combobox';
import { Dictionary, DictionaryNode, findDictionary } from '../dictionaries.mock';
import { isSearchable } from '../select-options';
import { FieldBase } from './field-base';

/** Levels to render for a selected path: level i+1 shows only when level i is chosen and has children. */
export function cascadeLevels(
  dict: Dictionary,
  path: readonly string[],
): { label: string; options: string[] }[] {
  const levels: { label: string; options: string[] }[] = [];
  let nodes: DictionaryNode[] | undefined = dict.items;
  for (let i = 0; nodes?.length && i < dict.levels.length; i++) {
    levels.push({ label: dict.levels[i], options: nodes.map((n) => n.name) });
    nodes = nodes.find((n) => n.name === path[i])?.children;
  }
  return levels;
}

@Component({
  selector: 'app-dictionary-cascade-field',
  imports: [Combobox],
  template: `
    <div
      role="group"
      class="space-y-4"
      [attr.aria-labelledby]="showTitle() ? id() + '-title' : null"
    >
      @if (showTitle()) {
        <div [id]="id() + '-title'" class="text-label font-label">{{ label() }}</div>
      }
      @if (hasDescription()) {
        <div class="text-fg-muted" [id]="descId()" [innerHTML]="field().description"></div>
      }
      @for (level of levels(); track level.label; let i = $index) {
        <app-combobox
          [label]="level.label"
          [options]="level.options"
          [searchable]="searchable(level.options.length)"
          [describedBy]="i === 0 ? describedBy() : null"
          [value]="value()[i] ?? ''"
          (valueChange)="choose(i, $event)"
        />
      }
    </div>
  `,
  host: { class: 'block' },
})
export class DictionaryCascadeField extends FieldBase<string[]> {
  protected readonly levels = computed(() => {
    const dict = findDictionary(this.field().dictionaryName);
    return dict ? cascadeLevels(dict, this.value()) : [];
  });
  // A title equal to the dictionary name is a technical leftover, not a legend.
  protected readonly showTitle = computed(
    () => this.hasTitle() && this.label() !== this.field().dictionaryName,
  );

  protected searchable(count: number): boolean {
    return isSearchable(this.field(), count);
  }

  /** An empty value (the clear button) truncates the path from this level down. */
  protected choose(level: number, v: string): void {
    this.set([...this.value().slice(0, level), v].filter(Boolean));
  }
}
