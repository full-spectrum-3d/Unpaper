import { findDictionary } from './dictionaries.mock';
import { FormField } from './form-definition';

const hasOptions = (field: FormField) => !!field.options?.length;

/** Multi-level dictionary (TERYT) without explicit options renders as a cascade. */
export const isCascade = (field: FormField): boolean =>
  !hasOptions(field) && (findDictionary(field.dictionaryName)?.levels.length ?? 0) > 1;

/** Explicit options win; otherwise the dictionary's top level. */
export const selectOptions = (field: FormField): string[] =>
  hasOptions(field)
    ? field.options!.map((o) => o.name)
    : (findDictionary(field.dictionaryName)?.items.map((i) => i.name) ?? []);

export const isSearchable = (field: FormField, optionCount: number): boolean =>
  field.searchEnabled === true || optionCount > 20;
