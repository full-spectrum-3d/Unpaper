import { describe, expect, it, vi } from 'vitest';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { FormDefinition, FormField, Question } from './form-definition';
import { evaluateVisibility } from './visibility';

const def = nadplata as unknown as FormDefinition;

function fieldsOf(d: FormDefinition): FormField[] {
  const out: FormField[] = [];
  const visit = (qs: Question[]) =>
    qs.forEach(({ field }) => {
      out.push(field);
      visit(field.repeatingSectionGrid ?? []);
    });
  d.tabs.forEach((t) => visit(t.questions));
  return out;
}

const idOf = (techName: string, d = def) => fieldsOf(d).find((f) => f.techName === techName)!.id;

const syntheticDef = (states: { type: string; query: string }[]): FormDefinition => ({
  title: 't',
  flow: { links: [] },
  tabs: [
    {
      id: 'tab',
      title: 'Dane',
      type: 'MAIN',
      questions: [
        {
          x: 0,
          y: 0,
          rows: 1,
          cols: 1,
          field: { id: 'f1', type: 'TEXT_FIELD', techName: 'broken_field', title: 'F', states },
        },
      ],
    },
  ],
});

describe('evaluateVisibility', () => {
  it('default shows only base sections', async () => {
    const hidden = await evaluateVisibility(def, new Map());
    for (const t of [
      'dane_podmiotu',
      'adres_siedziby',
      'potwierdzenie_ze_jestes_reprezentantem',
      'dane_innej_osoby',
      'adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem',
      'pelnomocnictwo',
      'oplata_skarbowa_pelnomocnictwo_1',
      'oplata_skarbowa_pelnomocnictwo_2',
      'wybierz_jako_kto_wnioskujesz',
    ])
      expect(hidden.has(idOf(t)), t).toBe(true);
    for (const t of [
      'urzad_do_ktorego_jest_skladany_wniosek',
      'podmiot_wniosku',
      'twoje_dane',
      'adres_zamieszkania',
    ])
      expect(hidden.has(idOf(t)), t).toBe(false);
  });

  it('other person shows its sections', async () => {
    const answers = new Map([[idOf('wybierz_w_czyim_imieniu_wnioskujesz'), 'Innej osoby']]);
    const hidden = await evaluateVisibility(def, answers);
    for (const t of [
      'dane_innej_osoby',
      'adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem',
      'pelnomocnictwo',
      'oplata_skarbowa_pelnomocnictwo_1',
    ])
      expect(hidden.has(idOf(t)), t).toBe(false);
    expect(hidden.has(idOf('dane_podmiotu'))).toBe(true);
  });

  it('hidden section hides children', async () => {
    const hidden = await evaluateVisibility(def, new Map());
    expect(hidden.has(idOf('nip'))).toBe(true);
    expect(hidden.has(idOf('nazwisko_inna_osoba'))).toBe(true);
  });

  it('HIDE true hides', async () => {
    const hidden = await evaluateVisibility(
      syntheticDef([{ type: 'HIDE', query: '1 = 1' }]),
      new Map(),
    );
    expect(hidden.has('f1')).toBe(true);
  });

  it('fail-open on broken query', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const hidden = await evaluateVisibility(
      syntheticDef([{ type: 'SHOW', query: '(' }]),
      new Map(),
    );
    expect(hidden.has('f1')).toBe(false);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('broken_field'), expect.anything());
    warn.mockRestore();
  });

  it('warns once per broken query, not on every evaluation', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const d = syntheticDef([{ type: 'SHOW', query: '(((' }]);
    await evaluateVisibility(d, new Map());
    await evaluateVisibility(d, new Map());
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });
});
