import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AnswersStore } from '../answers-store';
import { FieldHost } from '../field-host';
import { FormField } from '../form-definition';
import { FormState } from '../form-state';

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
  readOnly: 'readonly' | 'disabled' | 'combobox';
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
    readOnly: 'disabled',
    nameEl: labelledBy('fieldset'),
  },
  {
    name: 'CHECKBOX without options',
    field: { type: 'CHECKBOX' },
    describer: input,
    controls: (el) => [input(el)],
    readOnly: 'disabled',
    nameEl: (el) => input(el).closest('label')!,
  },
  {
    name: 'CHECKBOX with options',
    field: { type: 'CHECKBOX', options: opts },
    describer: (el) => q(el, 'fieldset'),
    controls: (el) => qa(el, 'input[type=checkbox]'),
    readOnly: 'disabled',
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
    readOnly: 'disabled',
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
        for (const ctl of controls) expect(ctl.getAttribute('aria-invalid')).toBe('true');
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
