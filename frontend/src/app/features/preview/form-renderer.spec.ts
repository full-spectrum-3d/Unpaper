import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import numerPorzadkowy from '../import/mock-forms/numer-porzadkowy.json';
import { FormDefinition, FormField } from './form-definition';
import { FormRenderer, STATES_EVALUATOR } from './form-renderer';
import { FieldStates, evaluateStates } from './visibility';

let impl: undefined | ((call: number) => Promise<FieldStates> | undefined);
let calls = 0;
let settled = 0;
const evaluator: typeof evaluateStates = async (...args) => {
  const result = await (impl?.(++calls) ?? evaluateStates(...args));
  settled++;
  return result;
};

describe('FormRenderer visibility', () => {
  let fixture: ComponentFixture<FormRenderer>;
  const el = () => fixture.nativeElement as HTMLElement;
  const radio = (name: string) =>
    [...el().querySelectorAll<HTMLInputElement>('input[type=radio]')].find(
      (r) => r.value === name,
    )!;
  const hasHeading = (name: string) =>
    [...el().querySelectorAll('h4')].some((h) => h.textContent?.trim() === name);

  const create = async () => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: STATES_EVALUATOR, useValue: evaluator },
      ],
    });
    fixture = TestBed.createComponent(FormRenderer);
    fixture.componentRef.setInput('definition', nadplata as unknown as FormDefinition);
    await fixture.whenStable();
  };
  const tick = async () => {
    fixture.detectChanges();
    await Promise.resolve();
  };

  beforeEach(() => {
    impl = undefined;
    calls = 0;
    settled = 0;
  });

  it('shows a conditional section once its answer is given', async () => {
    await create();
    expect(hasHeading('Dane innej osoby')).toBe(false);
    radio('Innej osoby').click();
    await fixture.whenStable();
    expect(hasHeading('Dane innej osoby')).toBe(true);
  });

  it('latest answers win: a slower, older evaluation never overwrites a newer one', async () => {
    let releaseStale!: (states: FieldStates) => void;
    // Call 1 is the initial evaluation, call 2 the stale one (held back), later calls are real.
    impl = (call) => (call === 2 ? new Promise((resolve) => (releaseStale = resolve)) : undefined);
    await create();

    radio('Innej osoby').click();
    await tick(); // evaluation 2 starts and stays pending
    radio('Swoim').click();
    await tick(); // evaluation 3 starts with the newer answers
    await vi.waitFor(() => expect(calls).toBe(3));
    await vi.waitFor(() => expect(settled).toBe(2)); // evaluations 1 and 3 are done, 2 is held
    fixture.detectChanges();
    expect(hasHeading('Dane innej osoby')).toBe(false);

    releaseStale({ hidden: new Set(), readOnly: new Set() }); // stale result would show "Dane innej osoby"
    await new Promise((resolve) => setTimeout(resolve)); // let the stale evaluation settle
    fixture.detectChanges();
    expect(hasHeading('Dane innej osoby')).toBe(false);
  });

  it('fails open when evaluation throws', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    impl = () => Promise.reject(new Error('boom'));
    await create();
    expect(warn).toHaveBeenCalled();
    expect(hasHeading('Dane innej osoby')).toBe(true);
    warn.mockRestore();
  });

  it('hides the TERYT cascade when the country is cleared', async () => {
    await create();
    const combo = (name: string) =>
      [...el().querySelectorAll<HTMLInputElement>('input[role=combobox]')].find(
        (i) => el().querySelector(`label[for="${i.id}"]`)?.textContent?.trim() === name,
      );
    expect(combo('Kraj')?.value).toBe('Polska');
    expect(combo('Województwo')).toBeDefined();

    el().querySelector<HTMLButtonElement>('button[aria-label="Wyczyść: Kraj"]')!.click();
    await fixture.whenStable();
    expect(combo('Województwo')).toBeUndefined();
  });

  it('keeps the TERYT path when the cascade is hidden and shown again', async () => {
    await create();
    const combo = (name: string) =>
      [...el().querySelectorAll<HTMLInputElement>('input[role=combobox]')].find(
        (i) => el().querySelector(`label[for="${i.id}"]`)?.textContent?.trim() === name,
      );
    const pick = async (name: string, option: string) => {
      combo(name)!.click();
      await fixture.whenStable();
      [...el().querySelectorAll<HTMLElement>('[role=option]')]
        .find((o) => o.textContent?.trim() === option)!
        .click();
      await fixture.whenStable();
    };

    await pick('Województwo', 'mazowieckie');
    el().querySelector<HTMLButtonElement>('button[aria-label="Wyczyść: Kraj"]')!.click();
    await fixture.whenStable();
    expect(combo('Województwo')).toBeUndefined();

    await pick('Kraj', 'Polska');
    expect(combo('Województwo')?.value).toBe('mazowieckie');
    expect(combo('Powiat')).toBeDefined();
  });
});

describe('FormRenderer step validation', () => {
  const q = (field: Partial<FormField> & { id: string }, y = 0) => ({
    x: 0,
    y,
    rows: 1,
    cols: 1,
    field: { type: 'TEXT_FIELD', techName: field.id, title: field.id, ...field } as FormField,
  });
  const showPowod = `("Tak" in tabs['Dane' in title].questions['sek' in field.techName].field.repeatingSectionGrid['czy' in field.techName].field.__userAnswer)`;
  const def: FormDefinition = {
    title: 'Test',
    flow: { links: [{ source: 't1', target: 't2' }] },
    tabs: [
      {
        id: 't1',
        title: 'Dane',
        type: 'MAIN',
        questions: [
          q({
            id: 'sek',
            type: 'SECTION',
            repeatingSectionGrid: [
              // The tooltip button precedes the input; focus must still land on the input.
              q({ id: 'imie', validation: ['REQUIRED'], tooltipMessage: 'Pomoc' }, 0),
              q({ id: 'nip', validation: ['NIP'] }, 1),
              q(
                {
                  id: 'czy',
                  type: 'RADIO',
                  options: [
                    { id: 'o1', name: 'Tak' },
                    { id: 'o2', name: 'Nie' },
                  ],
                },
                2,
              ),
              q(
                {
                  id: 'powod',
                  validation: ['REQUIRED'],
                  states: [{ type: 'SHOW', query: showPowod }],
                },
                3,
              ),
            ],
          }),
        ],
      },
      { id: 't2', title: 'Dalsze', type: 'MAIN', questions: [q({ id: 'x2' })] },
    ],
  };

  let fixture: ComponentFixture<FormRenderer>;
  const el = () => fixture.nativeElement as HTMLElement;
  const host = (id: string) => el().querySelector(`[data-field-id="${id}"]`);
  const input = (id: string) => host(id)?.querySelector('input') as HTMLInputElement;
  const error = (id: string) =>
    host(id)?.querySelector('.text-danger')?.textContent?.trim() ?? null;
  const step = () => el().querySelector('h3')?.textContent?.trim() ?? '';
  const button = (name: string) =>
    [...el().querySelectorAll('button')].find((b) => b.textContent?.trim() === name)!;
  const type = async (id: string, value: string) => {
    input(id).value = value;
    input(id).dispatchEvent(new Event('input'));
    await fixture.whenStable();
  };
  const click = async (name: string) => {
    button(name).click();
    await fixture.whenStable();
  };
  const choose = async (name: string) => {
    host('czy')!
      .querySelectorAll<HTMLInputElement>('input[type=radio]')
      .forEach((r) => r.value === name && r.click());
    await fixture.whenStable();
  };

  const create = async (stable = true) => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: STATES_EVALUATOR, useValue: evaluator },
      ],
    });
    fixture = TestBed.createComponent(FormRenderer);
    fixture.componentRef.setInput('definition', def);
    if (stable) await fixture.whenStable();
    else fixture.detectChanges();
  };

  beforeEach(() => {
    impl = undefined;
  });

  it('stays on the step, shows the error and focuses the first invalid field', async () => {
    await create();
    await click('Dalej');
    expect(step()).toBe('Krok 1 z 2: Dane');
    expect(error('imie')).toBe('✕ Uzupełnij to pole');
    expect(document.activeElement).toBe(input('imie'));
  });

  it('re-validates live once errors are shown', async () => {
    await create();
    await click('Dalej');
    await type('imie', 'Jan');
    expect(error('imie')).toBeNull();
    await type('nip', '123');
    expect(error('nip')).toBe('✕ Wpisz poprawny NIP: 10 cyfr');
  });

  it('shows errors of fields that appear and ignores fields that hide', async () => {
    await create();
    await click('Dalej');
    await choose('Tak');
    expect(error('powod')).toBe('✕ Uzupełnij to pole');
    await choose('Nie');
    expect(host('powod')).toBeNull();
    await type('imie', 'Jan');
    await type('nip', '1234563218');
    await click('Dalej');
    expect(step()).toBe('Krok 2 z 2: Dalsze');
  });

  it('uses the initially hidden fields before the first evaluation', async () => {
    const held: ((s: FieldStates) => void)[] = [];
    impl = () => new Promise((resolve) => held.push(resolve));
    await create(false);
    input('imie').value = 'Jan';
    input('imie').dispatchEvent(new Event('input'));
    button('Dalej').click();
    fixture.detectChanges();
    expect(step()).toBe('Krok 2 z 2: Dalsze');
    impl = undefined; // evaluations not started yet run for real
    held.forEach((release) => release({ hidden: new Set(), readOnly: new Set() }));
    await fixture.whenStable();
  });

  it('does not show errors after going back', async () => {
    await create();
    await type('imie', 'Jan');
    await click('Dalej');
    await click('Wstecz');
    await type('imie', '');
    expect(step()).toBe('Krok 1 z 2: Dane');
    expect(error('imie')).toBeNull();
  });

  it('clears errors on abort', async () => {
    await create();
    await click('Dalej');
    expect(error('imie')).not.toBeNull();
    await click('Przerwij wypełnianie');
    expect(error('imie')).toBeNull();
  });
});

describe('FormRenderer on the "Nadpłata podatku" mock', () => {
  const fields: FormField[] = [];
  const collect = (list: { field: FormField }[]) =>
    list.forEach(({ field }) => {
      fields.push(field);
      collect(field.repeatingSectionGrid ?? []);
    });
  (nadplata as unknown as FormDefinition).tabs.forEach((t) => collect(t.questions));
  const validation = (techName: string) => fields.find((f) => f.techName === techName)?.validation;

  it('has an array validation on every field of both mocks', () => {
    const all: FormField[] = [];
    const walk = (list: { field: FormField }[]) =>
      list.forEach(({ field }) => {
        all.push(field);
        walk(field.repeatingSectionGrid ?? []);
      });
    [nadplata, numerPorzadkowy].forEach((m) =>
      (m as unknown as FormDefinition).tabs.forEach((t) => walk(t.questions)),
    );
    expect(all.length).toBeGreaterThan(100);
    expect(all.filter((f) => !Array.isArray(f.validation)).map((f) => f.techName)).toEqual([]);
  });

  it('has backend-style validators', () => {
    expect(validation('nip')).toEqual(['REQUIRED', 'NIP']);
    expect(validation('kod_pocztowy')).toEqual(['REQUIRED', 'ZIP_CODE']);
    expect(validation('adres_e_mail')).toEqual(['EMAIL']);
    expect(validation('kwota')).toEqual(['REQUIRED']);
    expect(validation('numer_lokalu')).toEqual([]);
  });

  it('blocks "Dalej" on step 1, focuses the first invalid field and accepts registry values', async () => {
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(FormRenderer);
    fixture.componentRef.setInput('definition', nadplata as unknown as FormDefinition);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Dalej')!.click();
    await fixture.whenStable();

    expect(el.querySelector('h3')?.textContent?.trim()).toBe('Krok 1 z 3: Dane');
    const invalid = el.querySelector<HTMLElement>('[aria-invalid="true"]');
    expect(invalid).not.toBeNull();
    expect(document.activeElement).toBe(invalid);
    const postCode = fields.find((f) => f.techName === 'kod_pocztowy')!.id;
    expect(el.querySelector(`[data-field-id="${postCode}"] input`)).toHaveProperty(
      'value',
      '00-001',
    );
    expect(el.querySelector(`[data-field-id="${postCode}"] [aria-invalid="true"]`)).toBeNull();
  });
});
