import { findDictionary } from './sample-dictionaries';
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

/** The import format has no search flag, so long lists get a search box. */
export const isSearchable = (optionCount: number): boolean => optionCount > 20;
