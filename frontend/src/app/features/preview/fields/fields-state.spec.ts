import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AnswersStore } from '../answers-store';
import { FieldHost } from '../field-host';
import { FormField } from '../form-definition';
import { FormState } from '../form-state';
import { autocompleteFor } from './text';

type El = HTMLElement;
const q = <T extends Element = El>(root: El, sel: string) => root.querySelector<T>(sel)!;
const qa = <T extends Element = El>(root: El, sel: string) => [...root.querySelectorAll<T>(sel)];

const opts = [
  { id: 'a', name: 'A' },
  { id: 'b', name: 'B' },
];

interface Case {
  name: string;
  field: Partial<FormField>;
  value?: unknown;
  /** Element whose aria-describedby must reference the error. */
  describer: (el: El) => El;
  /** Controls that must carry aria-invalid / readonly-or-disabled. */
  controls: (el: El) => El[];
  /** aria-readonly: choices stay focusable, clicks are blocked (radio: on the radiogroup). */
  readOnly: 'readonly' | 'disabled' | 'combobox' | 'aria-readonly';
  /** Element whose text is (part of) the field's accessible name; undefined = no title. */
  nameEl?: (el: El) => El;
}

const input = (el: El) => q(el, 'input, textarea');
const labelFor = (el: El) => q(el, `label[for="${input(el).id}"]`);
const labelledBy = (sel: string) => (el: El) =>
  q(el, '#' + q(el, sel).getAttribute('aria-labelledby'));

const cases: Case[] = [
  {
    name: 'TEXT_FIELD',
    field: { type: 'TEXT_FIELD' },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'readonly',
    nameEl: labelFor,
  },
  {
    name: 'NUMBER',
    field: { type: 'NUMBER' },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'readonly',
    nameEl: labelFor,
  },
  {
    name: 'TEXTAREA',
    field: { type: 'TEXTAREA' },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'readonly',
    nameEl: labelFor,
  },
  {
    name: 'DATEPICKER',
    field: { type: 'DATEPICKER' },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'readonly',
    nameEl: labelFor,
  },
  {
    name: 'SELECT',
    field: { type: 'SELECT', options: opts },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'combobox',
    nameEl: labelFor,
  },
  {
    name: 'TERYT cascade',
    field: { type: 'SELECT', title: 'Adres', dictionaryName: 'TERYT_4G_DOWODOWY' },
    value: ['mazowieckie'],
    // Error belongs to the first empty level: Powiat.
    describer: (el) => qa(el, 'input[role=combobox]')[1],
    controls: (el) => [qa(el, 'input[role=combobox]')[1]],
    readOnly: 'combobox',
    nameEl: labelledBy('[role=group]'),
  },
  {
    name: 'RADIO',
    field: { type: 'RADIO', options: opts },
    describer: (el) => q(el, 'fieldset'),
    controls: (el) => qa(el, 'input[type=radio]'),
    readOnly: 'aria-readonly',
    nameEl: labelledBy('fieldset'),
  },
  {
    name: 'CHECKBOX without options',
    field: { type: 'CHECKBOX' },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'aria-readonly',
    nameEl: (el) => input(el).closest('label')!,
  },
  {
    name: 'CHECKBOX with options',
    field: { type: 'CHECKBOX', options: opts },
    describer: (el) => q(el, 'fieldset'),
    controls: (el) => qa(el, 'input[type=checkbox]'),
    readOnly: 'aria-readonly',
    nameEl: labelledBy('fieldset'),
  },
  {
    name: 'CONSENT_SECTION',
    field: {
      type: 'CONSENT_SECTION',
      title: undefined,
      consentSectionConfig: {
        consents: [
          { description: 'Zgoda 1', required: true },
          { description: 'Zgoda 2', required: false },
        ],
      },
    },
    describer: (el) => q(el, 'fieldset'),
    controls: (el) => qa(el, 'input[type=checkbox]'),
    readOnly: 'aria-readonly',
  },
  {
    name: 'FILE_UPLOADER',
    field: { type: 'FILE_UPLOADER' },
    describer: (el) => q(el, 'button:not([aria-expanded])'),
    controls: (el) => [q(el, 'button:not([aria-expanded])')],
    readOnly: 'disabled',
    nameEl: (el) => q(el, '[id$="-label"]'),
  },
];

describe('preview fields: error, read-only, tooltip, registry tag', () => {
  let fixture: ComponentFixture<FieldHost>;
  let state: FormState;
  const el = () => fixture.nativeElement as El;

  const render = async (c: Case, extra: Partial<FormField> = {}, setup?: () => void) => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), AnswersStore, FormState],
    });
    state = TestBed.inject(FormState);
    const field = { id: 'f', techName: 'f', title: 'Pole', ...c.field, ...extra } as FormField;
    if (c.value !== undefined) TestBed.inject(AnswersStore).answer(field).set(c.value);
    setup?.();
    fixture = TestBed.createComponent(FieldHost);
    fixture.componentRef.setInput('field', field);
    await fixture.whenStable();
  };

  for (const c of cases) {
    describe(c.name, () => {
      it('shows the error and links it to the control', async () => {
        await render(c, {}, () => state.errors.set(new Map([['f', 'X']])));
        const msg = qa(el(), 'small').find((s) => s.textContent?.includes('X'))!;
        expect(msg).toBeTruthy();
        expect(msg.id).toBeTruthy();
        expect(c.describer(el()).getAttribute('aria-describedby')?.split(' ')).toContain(msg.id);
        const controls = c.controls(el());
        expect(controls.length).toBeGreaterThan(0);
        for (const ctl of controls) {
          expect(ctl.getAttribute('aria-invalid')).toBe('true');
          // Each choice is linked too: the fieldset's description is not announced on every input.
          if (c.readOnly === 'aria-readonly') {
            expect(ctl.getAttribute('aria-describedby')?.split(' ')).toContain(msg.id);
          }
        }
      });

      it('has no error markup without an error', async () => {
        await render(c);
        for (const ctl of c.controls(el())) expect(ctl.hasAttribute('aria-invalid')).toBe(false);
      });

      it('honours the READ_ONLY state', async () => {
        await render(c, {}, () => state.readOnly.set(new Set(['f'])));
        const controls = c.controls(el());
        if (c.readOnly === 'readonly') {
          for (const ctl of controls) expect((ctl as HTMLInputElement).readOnly).toBe(true);
        } else if (c.readOnly === 'disabled') {
          for (const ctl of controls) expect((ctl as HTMLInputElement).disabled).toBe(true);
        } else if (c.readOnly === 'aria-readonly') {
          for (const ctl of controls) {
            const box = ctl as HTMLInputElement;
            expect(box.disabled).toBe(false);
            const holder = box.type === 'radio' ? box.closest('[role=radiogroup]')! : box;
            expect(holder.getAttribute('aria-readonly')).toBe('true');
            box.click();
            await fixture.whenStable();
            expect(box.checked).toBe(false);
          }
        } else {
          controls[0].click();
          await fixture.whenStable();
          expect(controls[0].getAttribute('aria-expanded')).toBe('false');
          expect(qa(el(), '[role=option]')).toHaveLength(0);
        }
      });

      if (c.nameEl) {
        it('shows the tooltip disclosure', async () => {
          await render(c, { tooltipMessage: 'Pomoc' });
          const label = c.field.title ?? 'Pole';
          expect(q(el(), `button[aria-label="Więcej informacji: ${label}"]`)).toBeTruthy();
        });

        it('shows the registry tag as part of the name', async () => {
          await render(c, { defaultValueType: 'EXTERNAL_SYSTEM' });
          const visible = qa(el(), '[aria-hidden=true]').find(
            (s) => s.textContent?.trim() === 'dane z rejestru',
          );
          expect(visible).toBeTruthy();
          expect(c.nameEl!(el()).textContent).toContain('dane z rejestru');
        });
      } else {
        it('shows no tooltip or tag without a title', async () => {
          await render(c, { tooltipMessage: 'Pomoc', defaultValueType: 'EXTERNAL_SYSTEM' });
          expect(el().querySelector('button[aria-label^="Więcej informacji"]')).toBeNull();
          expect(el().textContent).not.toContain('dane z rejestru');
        });
      }
    });
  }
});

describe('preview fields: required', () => {
  const required = { id: 'f', techName: 'f', title: 'Pole', validation: ['REQUIRED'] };
  const render = async (field: Partial<FormField>) => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), AnswersStore, FormState],
    });
    const fixture = TestBed.createComponent(FieldHost);
    fixture.componentRef.setInput('field', { ...required, ...field } as FormField);
    await fixture.whenStable();
    return fixture.nativeElement as El;
  };

  for (const type of ['TEXT_FIELD', 'TEXTAREA', 'DATEPICKER', 'SELECT', 'CHECKBOX']) {
    it(`${type} carries aria-required and a visible asterisk`, async () => {
      const el = await render({ type, options: type === 'SELECT' ? opts : undefined });
      expect(q(el, 'input, textarea').getAttribute('aria-required')).toBe('true');
      const star = qa(el, '[aria-hidden=true]').find((s) => s.textContent?.trim() === '*');
      expect(star).toBeTruthy();
    });
  }

  it('RADIO marks the radiogroup', async () => {
    const el = await render({ type: 'RADIO', options: opts });
    expect(q(el, '[role=radiogroup]').getAttribute('aria-required')).toBe('true');
  });

  it('CHECKBOX group says it in the group name (role=group has no aria-required)', async () => {
    const el = await render({ type: 'CHECKBOX', options: opts });
    expect(labelledBy('fieldset')(el).textContent).toContain('(wymagane)');
  });

  it('FILE_UPLOADER names the field in its button', async () => {
    const el = await render({ type: 'FILE_UPLOADER' });
    expect(q(el, 'button').getAttribute('aria-label')).toBe(
      'Dodaj lub przeciągnij plik: Pole (wymagane)',
    );
  });

  it('is not marked without REQUIRED', async () => {
    const el = await render({ type: 'TEXT_FIELD', validation: [] });
    expect(q(el, 'input').hasAttribute('aria-required')).toBe(false);
    expect(el.textContent).not.toContain('*');
  });
});

describe('preview fields: smaller a11y details', () => {
  const render = async (field: Partial<FormField>) => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), AnswersStore, FormState],
    });
    const fixture = TestBed.createComponent(FieldHost);
    fixture.componentRef.setInput('field', { id: 'f', techName: 'f', title: 'Pole', ...field });
    await fixture.whenStable();
    return fixture;
  };

  it("autocomplete covers only the applicant's own data", () => {
    expect(autocompleteFor('imie')).toBe('given-name');
    expect(autocompleteFor('kod_pocztowy_zagranica')).toBe('postal-code');
    expect(autocompleteFor('adres_e_mail')).toBe('email');
    expect(autocompleteFor('nazwisko_inna_osoba')).toBeUndefined();
    expect(autocompleteFor('ulica_siedziba')).toBeUndefined();
    expect(autocompleteFor(undefined)).toBeUndefined();
  });

  it('sets autocomplete on the text input', async () => {
    const fixture = await render({ type: 'TEXT_FIELD', techName: 'nazwisko' });
    expect(q(fixture.nativeElement, 'input').getAttribute('autocomplete')).toBe('family-name');
  });

  it('nests section headings by depth, capped at h6', async () => {
    const section = (id: string, inner: FormField[] = []): FormField =>
      ({
        id,
        type: 'SECTION',
        techName: id,
        title: id,
        repeatingSectionGrid: inner.map((field, y) => ({ x: 0, y, rows: 1, cols: 1, field })),
      }) as FormField;
    const fixture = await render(section('a', [section('b', [section('c', [section('d')])])]));
    const el = fixture.nativeElement as El;
    expect(['h4', 'h5', 'h6'].map((h) => q(el, h).textContent?.trim())).toEqual(['a', 'b', 'c']);
    expect(qa(el, 'h6').map((h) => h.textContent?.trim())).toEqual(['c', 'd']);
  });

  it('textarea announces the character limit only near it', async () => {
    const fixture = await render({ type: 'TEXTAREA' });
    const el = fixture.nativeElement as El;
    const notice = () => q(el, 'p[aria-live]').textContent?.trim();
    expect(notice()).toBe('');
    TestBed.inject(AnswersStore)
      .answer({ id: 'f' } as FormField)
      .set('x'.repeat(7900));
    await fixture.whenStable();
    expect(notice()).toBe('Zostało mniej niż 200 znaków');
  });
});
