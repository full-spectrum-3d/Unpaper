import { describe, expect, it, vi } from 'vitest';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { FormDefinition, FormField, Question } from './form-definition';
import { evaluateStates } from './visibility';

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

describe('evaluateStates', () => {
  it('default shows only base sections', async () => {
    const { hidden } = await evaluateStates(def, new Map());
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
    const { hidden } = await evaluateStates(def, answers);
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
    const { hidden } = await evaluateStates(def, new Map());
    expect(hidden.has(idOf('nip'))).toBe(true);
    expect(hidden.has(idOf('nazwisko_inna_osoba'))).toBe(true);
  });

  it('HIDE true hides', async () => {
    const { hidden } = await evaluateStates(
      syntheticDef([{ type: 'HIDE', query: '1 = 1' }]),
      new Map(),
    );
    expect(hidden.has('f1')).toBe(true);
  });

  it('fail-open on broken query', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { hidden } = await evaluateStates(
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
    await evaluateStates(d, new Map());
    await evaluateStates(d, new Map());
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });

  it('READ_ONLY true marks the field, false does not', async () => {
    expect(
      (
        await evaluateStates(syntheticDef([{ type: 'READ_ONLY', query: '1 = 1' }]), new Map())
      ).readOnly.has('f1'),
    ).toBe(true);
    expect(
      (
        await evaluateStates(syntheticDef([{ type: 'READ_ONLY', query: '1 = 2' }]), new Map())
      ).readOnly.has('f1'),
    ).toBe(false);
  });

  it('READ_ONLY fails open on broken query', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { readOnly } = await evaluateStates(
      syntheticDef([{ type: 'READ_ONLY', query: '[[[' }]),
      new Map(),
    );
    expect(readOnly.has('f1')).toBe(false);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('broken_field'), expect.anything());
    warn.mockRestore();
  });

  it('hidden field is never read-only', async () => {
    const states = await evaluateStates(
      syntheticDef([
        { type: 'HIDE', query: '1 = 1' },
        { type: 'READ_ONLY', query: '1 = 1' },
      ]),
      new Map(),
    );
    expect(states.hidden.has('f1')).toBe(true);
    expect(states.readOnly.has('f1')).toBe(false);
  });

  it('a hidden field no longer keeps its dependants visible (A hides, B and C follow)', async () => {
    const answerOf = (techName: string) =>
      `tabs.questions[field.techName = '${techName}'].field.__userAnswer`;
    const q = (y: number, field: FormField): Question => ({ x: 0, y, rows: 1, cols: 1, field });
    const chain: FormDefinition = {
      title: 't',
      flow: { links: [] },
      tabs: [
        {
          id: 'tab',
          title: 'Dane',
          type: 'MAIN',
          questions: [
            q(0, {
              id: 'a',
              type: 'TEXT_FIELD',
              techName: 'a',
              title: 'A',
              states: [{ type: 'HIDE', query: '1 = 1' }],
            }),
            q(1, {
              id: 'b',
              type: 'TEXT_FIELD',
              techName: 'b',
              title: 'B',
              states: [{ type: 'SHOW', query: `${answerOf('a')} = 'x'` }],
            }),
            q(2, {
              id: 'c',
              type: 'TEXT_FIELD',
              techName: 'c',
              title: 'C',
              states: [{ type: 'SHOW', query: `${answerOf('b')} = 'y'` }],
            }),
          ],
        },
      ],
    };
    const { hidden } = await evaluateStates(
      chain,
      new Map([
        ['a', 'x'],
        ['b', 'y'],
      ]),
    );
    expect([...hidden].sort()).toEqual(['a', 'b', 'c']);
  });

  it('stops on a query that flips on its own answer', async () => {
    const flip = syntheticDef([{ type: 'HIDE', query: "tabs.questions.field.__userAnswer = 'x'" }]);
    await expect(evaluateStates(flip, new Map([['f1', 'x']]))).resolves.toBeDefined();
  });
});
