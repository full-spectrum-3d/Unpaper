import { FormDefinition, FormField, isFormDefinition } from '../preview/form-definition';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { sortQuestions } from '../preview/page-order';
import {
  addField,
  allQuestions,
  htmlToText,
  renameTechName,
  techNameError,
  moveField,
  removeField,
  reorderField,
  slugify,
  textToHtml,
  updateField,
} from './form-edit';

const def = nadplata as unknown as FormDefinition;
const fields = (d: FormDefinition): FormField[] =>
  d.tabs.flatMap((t) => [...allQuestions(t.questions)].map((q) => q.field));
const byName = (d: FormDefinition, techName: string) =>
  fields(d).find((f) => f.techName === techName)!;
const section = byName(def, 'dane_podmiotu');

describe('slugify', () => {
  it('transliterates Polish letters and collapses separators like the backend', () => {
    expect(slugify('  Żółć gęślą, łąka! ')).toBe('zolc_gesla_laka');
    expect(slugify('???')).toBe('pole');
    expect(slugify('a'.repeat(40) + ' ' + 'b'.repeat(40))).toBe('a'.repeat(40));
  });
});

describe('addField', () => {
  it('appends a field in a new full-width row at the end of the section', () => {
    const { definition, field } = addField(def, section.id, {
      type: 'NUMBER',
      title: ' Liczba pracowników ',
      required: true,
    });
    const grid = byName(definition, 'dane_podmiotu').repeatingSectionGrid!;
    const last = grid.at(-1)!;
    expect(last).toMatchObject({ x: 0, y: 2, rows: 1, cols: 3 });
    expect(last.field).toMatchObject({
      id: field.id,
      type: 'NUMBER',
      title: 'Liczba pracowników',
      techName: 'liczba_pracownikow',
      validation: ['REQUIRED'],
      options: [],
      states: [],
      readOnly: false,
      questionOrder: 2,
    });
    expect(field.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(isFormDefinition(definition)).toBe(true);
    // Immutable, with untouched parts shared.
    expect(byName(def, 'dane_podmiotu').repeatingSectionGrid).toHaveLength(2);
    expect(definition.tabs[1]).toBe(def.tabs[1]);
  });

  it('makes the techName unique within the form', () => {
    const one = addField(def, section.id, { type: 'TEXT_FIELD', title: 'Nazwa', required: false });
    expect(one.field.techName).toBe('nazwa_2');
    const two = addField(one.definition, section.id, {
      type: 'TEXT_FIELD',
      title: 'Nazwa',
      required: false,
    });
    expect(two.field.techName).toBe('nazwa_3');
  });

  it('gives choice fields options with ids and techNames', () => {
    const { field } = addField(def, section.id, {
      type: 'RADIO',
      title: 'Zgoda',
      required: false,
      options: ['Tak', 'Nie'],
    });
    expect(field.options).toEqual([
      { id: expect.any(String), name: 'Tak', techName: 'tak' },
      { id: expect.any(String), name: 'Nie', techName: 'nie' },
    ]);
  });
});

describe('updateField', () => {
  it('changes the title and keeps id and techName', () => {
    const nip = byName(def, 'nip');
    const next = byName(updateField(def, nip.id, { title: 'Numer NIP' }), 'nip');
    expect(next).toMatchObject({ id: nip.id, techName: 'nip', title: 'Numer NIP' });
  });

  it('drops validators the new type does not allow and keeps REQUIRED', () => {
    const nip = byName(def, 'nip');
    expect(nip.validation).toEqual(['REQUIRED', 'NIP']);
    const next = byName(updateField(def, nip.id, { type: 'NUMBER' }), 'nip');
    expect(next.type).toBe('NUMBER');
    expect(next.validation).toEqual(['REQUIRED']);
  });

  it('toggles REQUIRED', () => {
    const nip = byName(def, 'nip');
    const off = updateField(def, nip.id, { required: false });
    expect(byName(off, 'nip').validation).toEqual(['NIP']);
    expect(byName(updateField(off, nip.id, { required: true }), 'nip').validation).toEqual([
      'REQUIRED',
      'NIP',
    ]);
  });

  it('adds options when switching to a choice type and drops them and dictionary keys when leaving it', () => {
    const nip = byName(def, 'nip');
    const radio = byName(updateField(def, nip.id, { type: 'RADIO', options: ['A', 'B'] }), 'nip');
    expect(radio.options!.map((o) => o.name)).toEqual(['A', 'B']);

    const kraj = byName(def, 'kraj');
    expect(kraj.dictionaryName).toBeTruthy();
    const text = byName(updateField(def, kraj.id, { type: 'TEXT_FIELD' }), 'kraj') as FormField &
      Record<string, unknown>;
    expect(text.options).toEqual([]);
    expect(text.dictionaryName).toBeUndefined();
    expect(text.defaultValue).toBeUndefined();
  });

  it('fills placeholder options when a field becomes a choice without enough of them', () => {
    const nip = byName(def, 'nip');
    const select = byName(updateField(def, nip.id, { type: 'SELECT' }), 'nip');
    expect(select.options!.map((o) => o.name)).toEqual(['Opcja 1', 'Opcja 2']);
  });

  it('keeps ids of options whose name did not change', () => {
    const radio = byName(def, 'wybierz_w_czyim_imieniu_wnioskujesz');
    const [first] = radio.options!;
    const next = byName(
      updateField(def, radio.id, { options: [first.name, 'Nowa'] }),
      'wybierz_w_czyim_imieniu_wnioskujesz',
    );
    expect(next.options![0]).toBe(first);
    expect(next.options![1].name).toBe('Nowa');
  });
});

describe('removeField', () => {
  it('removes a field', () => {
    const nip = byName(def, 'nip');
    const { definition, droppedStatesOf } = removeField(def, nip.id);
    expect(fields(definition).some((f) => f.id === nip.id)).toBe(false);
    expect(droppedStatesOf).toEqual([]);
    expect(isFormDefinition(definition)).toBe(true);
  });

  it('removes a section with its children and drops conditions that referred to them', () => {
    const podmiot = byName(def, 'podmiot_wniosku');
    const { definition, droppedStatesOf } = removeField(def, podmiot.id);
    const names = fields(definition).map((f) => f.techName);
    expect(names).not.toContain('podmiot_wniosku');
    expect(names).not.toContain('wybierz_jako_kto_wnioskujesz');
    expect(droppedStatesOf.map((f) => f.techName)).toContain('dane_podmiotu');
    for (const f of fields(definition)) {
      for (const s of f.states ?? []) expect(s.query).not.toContain("'podmiot_wniosku'");
    }
    // Conditions on other fields stay.
    expect(byName(definition, 'ulica').states).toEqual(byName(def, 'ulica').states);
  });
});

describe('moveField', () => {
  const order = (d: FormDefinition, techName: string) =>
    sortQuestions(byName(d, techName).repeatingSectionGrid!).map((q) => q.field.techName);

  it('swaps a field with its on-screen neighbour, keeping slots and questionOrder in place', () => {
    const moved = moveField(def, byName(def, 'imie').id, 1);
    expect(order(moved, 'twoje_dane')).toEqual(['nazwisko', 'imie', 'numer_pesel']);
    const grid = sortQuestions(byName(moved, 'twoje_dane').repeatingSectionGrid!);
    expect(grid.map((q) => [q.y, q.field.questionOrder])).toEqual([
      [0, 0],
      [1, 1],
      [2, 2],
    ]);
    expect(isFormDefinition(moved)).toBe(true);
    expect(moved.tabs[1]).toBe(def.tabs[1]);
  });

  it('moves top-level sections with their children', () => {
    const moved = moveField(def, byName(def, 'podmiot_wniosku').id, -1);
    const top = sortQuestions(moved.tabs[0].questions).map((q) => q.field.techName);
    expect(top.slice(0, 2)).toEqual(['podmiot_wniosku', 'urzad_do_ktorego_jest_skladany_wniosek']);
    expect(order(moved, 'podmiot_wniosku')).toEqual(order(def, 'podmiot_wniosku'));
  });

  it('does nothing past either end', () => {
    expect(moveField(def, byName(def, 'imie').id, -1)).toBe(def);
    expect(moveField(def, byName(def, 'numer_pesel').id, 1)).toBe(def);
  });
});

describe('reorderField', () => {
  const order = (d: FormDefinition, techName: string) =>
    sortQuestions(byName(d, techName).repeatingSectionGrid!).map((q) => q.field.techName);

  it('moves a field over several positions, shifting the others between the slots', () => {
    const moved = reorderField(def, byName(def, 'imie').id, 2);
    expect(order(moved, 'twoje_dane')).toEqual(['nazwisko', 'numer_pesel', 'imie']);
    const grid = sortQuestions(byName(moved, 'twoje_dane').repeatingSectionGrid!);
    expect(grid.map((q) => [q.y, q.field.questionOrder])).toEqual([
      [0, 0],
      [1, 1],
      [2, 2],
    ]);
    expect(isFormDefinition(moved)).toBe(true);
    expect(reorderField(moved, byName(def, 'imie').id, 0)).toEqual(def);
  });

  it('does nothing for the same or an out-of-range position', () => {
    const id = byName(def, 'nazwisko').id;
    expect(reorderField(def, id, 1)).toBe(def);
    expect(reorderField(def, id, 3)).toBe(def);
    expect(reorderField(def, id, -1)).toBe(def);
  });
});

describe('text and HTML', () => {
  it('writes paragraphs like the backend and reads them back', () => {
    const html = textToHtml('Pierwszy <akapit>\nz nową linią\n\nDrugi');
    expect(html).toBe(
      '<html><head></head><body><p>Pierwszy &lt;akapit&gt;<br>z nową linią</p><p>Drugi</p></body></html>',
    );
    expect(htmlToText(html)).toBe('Pierwszy <akapit>\nz nową linią\n\nDrugi');
    expect(textToHtml('  \n ')).toBe('');
  });
});

describe('new field types', () => {
  it('adds a text block and an information section with their text in description', () => {
    const block = addField(def, section.id, {
      type: 'TEXT_BLOCK',
      title: '',
      required: true,
      content: 'Wypełnij drukowanymi literami.',
    });
    expect(block.field).toMatchObject({
      type: 'TEXT_BLOCK',
      title: '',
      techName: 'blok_tekstu',
      validation: [],
      description: '<html><head></head><body><p>Wypełnij drukowanymi literami.</p></body></html>',
    });
    const info = addField(def, section.id, {
      type: 'INFO_SECTION',
      title: 'Ważne',
      required: false,
      content: 'Opłata wynosi 17 zł.',
    });
    expect(htmlToText(info.field.description)).toBe('Opłata wynosi 17 zł.');
  });

  it('adds a consent section in the import document format', () => {
    const { field } = addField(def, section.id, {
      type: 'CONSENT_SECTION',
      title: '',
      required: false,
      consents: [{ text: 'Zgoda A' }, { text: 'Zgoda B' }],
      consentsRequired: false,
      consentFiles: ['klauzula.pdf'],
    });
    expect(field.consentSectionConfig).toEqual({
      consents: [{ description: textToHtml('Zgoda A') }, { description: textToHtml('Zgoda B') }],
      required: false,
      files: ['klauzula.pdf'],
    });
    expect(field.validation).toEqual([]);
  });

  it('adds a list with a predefined dictionary instead of options', () => {
    const { field } = addField(def, section.id, {
      type: 'SELECT',
      title: 'Kraj',
      required: true,
      options: ['x', 'y'],
      dictionary: { name: 'Kraje' },
    });
    expect(field).toMatchObject({ dictionaryName: 'Kraje', options: [], validation: ['REQUIRED'] });
    // Keys the import document does not define are not written.
    expect(Object.keys(field)).not.toContain('searchEnabled');
    expect(Object.keys(field)).not.toContain('multiLevelTree');
  });

  it('switches a list between a dictionary and own options', () => {
    const country = byName(def, 'nazwa');
    const select = updateField(def, country.id, { type: 'SELECT' });
    const withDict = updateField(select, country.id, {
      dictionary: { name: 'TERYT_DOWODOWY' },
    });
    expect(byName(withDict, 'nazwa')).toMatchObject({
      dictionaryName: 'TERYT_DOWODOWY',
      options: [],
    });
    const own = byName(updateField(withDict, country.id, { dictionary: null }), 'nazwa');
    expect(own.dictionaryName).toBeUndefined();
    expect(own.options!.map((o) => o.name)).toEqual(['Opcja 1', 'Opcja 2']);
    // A dictionary does not survive a change to another choice type.
    const radio = byName(updateField(withDict, country.id, { type: 'RADIO' }), 'nazwa');
    expect(radio.dictionaryName).toBeUndefined();
    expect(radio.options!.length).toBe(2);
  });

  it('keeps an importable shape when switching to and from content and consent types', () => {
    const nip = byName(def, 'nip');
    const block = byName(updateField(def, nip.id, { type: 'INFO_SECTION' }), 'nip');
    expect(block).toMatchObject({ type: 'INFO_SECTION', validation: [], options: [] });
    expect(htmlToText(block.description)).toBe('NIP');
    const consent = byName(updateField(def, nip.id, { type: 'CONSENT_SECTION' }), 'nip');
    expect(consent.consentSectionConfig).toEqual({
      consents: [{ description: textToHtml('NIP') }],
      required: true,
      files: [],
    });
    const back = updateField(updateField(def, nip.id, { type: 'CONSENT_SECTION' }), nip.id, {
      type: 'TEXT_FIELD',
    });
    expect(byName(back, 'nip').consentSectionConfig).toBeUndefined();
    expect(isFormDefinition(back)).toBe(true);
  });

  it('keeps the HTML of consents whose text did not change', () => {
    const zgoda = byName(def, 'zgoda');
    const original = zgoda.consentSectionConfig!.consents[0];
    const text = htmlToText(original.description);
    const next = updateField(def, zgoda.id, {
      consents: [{ text }, { text: 'Oświadczam, że dane są prawdziwe.' }],
    });
    const consents = byName(next, 'zgoda').consentSectionConfig!.consents;
    expect(consents[0].description).toBe(original.description);
    expect(consents[1]).toEqual({ description: textToHtml('Oświadczam, że dane są prawdziwe.') });
  });

  it('replaces the text of a text block', () => {
    const block = byName(def, 'podglad_1');
    const next = updateField(def, block.id, { content: 'Nowa treść' });
    expect(byName(next, 'podglad_1').description).toBe(textToHtml('Nowa treść'));
  });
});

describe('format validators', () => {
  it('replaces the format validator of a text field and keeps REQUIRED', () => {
    const nip = byName(def, 'nip');
    expect(byName(updateField(def, nip.id, { format: 'REGON' }), 'nip').validation).toEqual([
      'REQUIRED',
      'REGON',
    ]);
    expect(byName(updateField(def, nip.id, { format: null }), 'nip').validation).toEqual([
      'REQUIRED',
    ]);
    const email = byName(def, 'adres_e_mail');
    const both = updateField(updateField(def, email.id, { required: true }), email.id, {
      format: 'ADE',
    });
    expect(byName(both, 'adres_e_mail').validation).toEqual(['REQUIRED', 'ADE']);
  });

  it('ignores a format for other types and drops it when the type changes', () => {
    const nip = byName(def, 'nip');
    const number = updateField(def, nip.id, { type: 'NUMBER' });
    expect(byName(number, 'nip').validation).toEqual(['REQUIRED']);
    expect(byName(updateField(number, nip.id, { format: 'PESEL' }), 'nip').validation).toEqual([
      'REQUIRED',
    ]);
  });

  it('adds a text field with a format validator', () => {
    const { field } = addField(def, section.id, {
      type: 'TEXT_FIELD',
      title: 'REGON',
      required: true,
      format: 'REGON',
    });
    expect(field.validation).toEqual(['REQUIRED', 'REGON']);
    const number = addField(def, section.id, {
      type: 'NUMBER',
      title: 'Ile',
      required: false,
      format: 'REGON',
    });
    expect(number.field.validation).toEqual([]);
  });
});

describe('component spec settings', () => {
  it('renames a techName together with the conditions that use it', () => {
    const kraj = byName(def, 'kraj');
    const renamed = renameTechName(def, kraj.id, 'panstwo');
    expect(byName(renamed, 'panstwo').id).toBe(kraj.id);
    const query = byName(renamed, 'ulica').states![0].query;
    expect(query).toContain("'panstwo' in field.techName");
    expect(query).not.toContain("'kraj'");
    // Other names that merely contain the old one stay.
    expect(byName(renamed, 'kraj_siedziba')).toBeDefined();
    expect(isFormDefinition(renamed)).toBe(true);
  });

  it('checks techName format and uniqueness', () => {
    const taken = new Set(['nip']);
    expect(techNameError('nip', taken)).toContain('już użyta');
    expect(techNameError('Nip', taken)).toContain('małe litery');
    expect(techNameError('', taken)).toBe('Podaj nazwę techniczną.');
    expect(techNameError('a'.repeat(61), taken)).toContain('60');
    expect(techNameError('nip_2', taken)).toBeNull();
  });

  it('sets default values: fixed text, list option, initial data', () => {
    const nazwa = byName(def, 'nazwa');
    const fixed = updateField(def, nazwa.id, { defaultValue: { kind: 'value', value: 'ACME' } });
    expect(byName(fixed, 'nazwa')).toMatchObject({ defaultValue: 'ACME' });
    expect(byName(fixed, 'nazwa').defaultValueType).toBeUndefined();
    const initial = updateField(fixed, nazwa.id, {
      defaultValue: { kind: 'initial', ref: 'PESEL.name', editable: false },
    });
    expect(byName(initial, 'nazwa')).toMatchObject({
      defaultValue: 'PESEL.name',
      defaultValueType: 'EXTERNAL_SYSTEM',
      readOnly: true,
    });
    const none = byName(
      updateField(initial, nazwa.id, { defaultValue: { kind: 'none' } }),
      'nazwa',
    );
    expect(none.defaultValue).toBeUndefined();
    expect(none.defaultValueType).toBeUndefined();
    // A type change drops a default made for the old control.
    const retyped = byName(updateField(initial, nazwa.id, { type: 'FILE_UPLOADER' }), 'nazwa');
    expect(retyped).toMatchObject({ readOnly: false });
    expect(retyped.defaultValueType).toBeUndefined();
  });

  it('sets description, read-only and states', () => {
    const kraj = byName(def, 'kraj');
    const changed = [
      { description: 'Kraj zamieszkania' },
      { readOnly: true },
      { states: [{ type: 'READ_ONLY', query: '$exists(x)' }] },
    ].reduce((d, patch) => updateField(d, kraj.id, patch), def);
    expect(byName(changed, 'kraj')).toMatchObject({
      description: textToHtml('Kraj zamieszkania'),
      readOnly: true,
      states: [{ type: 'READ_ONLY', query: '$exists(x)' }],
    });
  });

  it('sets the requiredness and the files of a consent section', () => {
    const zgoda = byName(def, 'zgoda');
    const optional = updateField(def, zgoda.id, { consentsRequired: false });
    const withFiles = updateField(optional, zgoda.id, { consentFiles: ['klauzula.pdf'] });
    expect(byName(withFiles, 'zgoda').consentSectionConfig).toMatchObject({
      required: false,
      files: ['klauzula.pdf'],
      consents: zgoda.consentSectionConfig!.consents,
    });
    // Editing the consents keeps both.
    const edited = updateField(withFiles, zgoda.id, { consents: [{ text: 'Jedna' }] });
    expect(byName(edited, 'zgoda').consentSectionConfig).toMatchObject({
      required: false,
      files: ['klauzula.pdf'],
    });
  });
});
