import { FormDefinition, FormField, isFormDefinition } from '../preview/form-definition';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { sortQuestions } from '../preview/page-order';
import { addField, allQuestions, moveField, removeField, slugify, updateField } from './form-edit';

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
    expect(text['searchEnabled']).toBeUndefined();
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
