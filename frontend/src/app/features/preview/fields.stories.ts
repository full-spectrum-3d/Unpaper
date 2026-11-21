import { Component, effect, inject, input } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, within } from 'storybook/test';
import { AnswersStore } from './answers-store';
import { FormField, Question } from './form-definition';
import { FormState } from './form-state';
import { RendererGrid } from './renderer-grid';

@Component({
  selector: 'app-fields-harness',
  imports: [RendererGrid],
  providers: [AnswersStore, FormState],
  template: `<app-renderer-grid [questions]="questions()" [hidden]="hidden()" />`,
})
class FieldsHarness {
  readonly questions = input.required<Question[]>();
  readonly hidden = input<ReadonlySet<string>>(new Set());
  readonly errors = input<ReadonlyMap<string, string>>(new Map());
  readonly readOnly = input<ReadonlySet<string>>(new Set());

  constructor() {
    // Stories stand in for FormRenderer, the only writer of FormState.
    const state = inject(FormState);
    effect(() => state.errors.set(this.errors()));
    effect(() => state.readOnly.set(this.readOnly()));
  }
}

const f = (id: string, type: string, extra: Partial<FormField> = {}): FormField => ({
  id,
  type,
  techName: id,
  title: `Pole ${id}`,
  ...extra,
});
const q = (field: FormField, y: number, cols = 3, x = 0): Question => ({
  x,
  y,
  rows: 1,
  cols,
  field,
});
const opts = ['Swoim', 'Innej osoby', 'Firmy'].map((name, i) => ({ id: `o${i}`, name }));

const meta: Meta<FieldsHarness> = {
  title: 'Podgląd/Pola',
  component: FieldsHarness,
  globals: { theme: 'preview' },
};
export default meta;
type Story = StoryObj<FieldsHarness>;

const allTypes: Question[] = [
  f('urzad', 'TEXT_FIELD', {
    title: 'Urząd',
    readOnly: true,
    defaultValue: 'Urząd Gminy Ulan-Majorat',
  }),
  f('kwota', 'NUMBER', { title: 'Kwota' }),
  f('opis', 'TEXTAREA', { title: 'Opis', description: '<p>Opisz sprawę</p>' }),
  f('radio', 'RADIO', {
    title: 'W czyim imieniu',
    description: '<p>Wybierz jedno</p>',
    options: opts,
  }),
  f('sel', 'SELECT', { title: 'Wybór', options: opts }),
  f('dict', 'SELECT', {
    title: 'Kraj',
    dictionaryName: 'Kraje',
    defaultValue: ['Polska'],
    searchEnabled: true,
  }),
  f('teryt', 'SELECT', {
    title: 'TERYT_4G_DOWODOWY',
    dictionaryName: 'TERYT_4G_DOWODOWY',
    searchEnabled: true,
    defaultValue: [],
  }),
  f('chk', 'CHECKBOX', { title: 'Zgoda ogólna' }),
  f('data', 'DATEPICKER', { title: 'Data' }),
  f('plik', 'FILE_UPLOADER', { title: 'Załącznik' }),
  f('blok', 'TEXT_BLOCK', { description: '<p>Ważne</p><script>x</script>' }),
  f('zgody', 'CONSENT_SECTION', {
    title: 'Zgody',
    consentSectionConfig: {
      consents: [{ description: '<b>Zgoda</b> na kontakt', required: true }],
    },
  }),
  f('foo', 'FOO', { title: 'Dziwne' }),
].map((field, i) => q(field, i));

export const AllTypes: Story = {
  args: { questions: allTypes },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const urzad = c.getByLabelText('Urząd');
    expect(urzad).toHaveAttribute('readonly');
    expect(urzad).toHaveValue('Urząd Gminy Ulan-Majorat');
    expect(c.getByLabelText('Kwota')).toHaveAttribute('inputmode', 'decimal');

    expect(c.getByLabelText('Opis')).toHaveAccessibleDescription('Opisz sprawę 0/8000');
    await userEvent.type(c.getByLabelText('Opis'), 'abc');
    expect(c.getByText('3/8000')).toBeVisible();

    const radios = within(c.getByRole('group', { name: 'W czyim imieniu' })).getAllByRole('radio');
    expect(radios).toHaveLength(3);
    expect(c.getByRole('group', { name: 'W czyim imieniu' })).toHaveAccessibleDescription(
      'Wybierz jedno',
    );
    await userEvent.click(radios[1]);
    expect(radios[1]).toBeChecked();

    const sel = c.getByRole('combobox', { name: 'Wybór' });
    await userEvent.click(sel);
    expect(c.getAllByRole('option').length).toBeGreaterThan(0);
    await userEvent.keyboard('{Escape}');

    const kraj = c.getByRole('combobox', { name: 'Kraj' });
    expect(kraj).toHaveValue('Polska');
    await userEvent.click(kraj);
    expect(c.getByRole('option', { name: 'Polska' })).toBeVisible();
    await userEvent.keyboard('{Escape}');

    expect(c.queryByText('TERYT_4G_DOWODOWY')).toBeNull();
    expect(c.queryByRole('combobox', { name: 'Powiat' })).toBeNull();
    await userEvent.click(c.getByRole('combobox', { name: 'Województwo' }));
    await userEvent.click(c.getByRole('option', { name: 'mazowieckie' }));
    expect(c.getByRole('combobox', { name: 'Powiat' })).toBeVisible();

    const chk = c.getByRole('checkbox', { name: 'Zgoda ogólna' });
    await userEvent.click(chk);
    expect(chk).toBeChecked();
    expect(c.getByLabelText('Data')).toHaveAttribute('type', 'date');

    expect(c.getByRole('button', { name: 'Dodaj lub przeciągnij plik' })).toBeVisible();
    await userEvent.upload(
      canvasElement.querySelector('input[type=file]') as HTMLInputElement,
      new File(['x'], 'a.pdf', { type: 'application/pdf' }),
    );
    expect(c.getByText('a.pdf')).toBeVisible();
    expect(c.getByText('10 MB')).toBeVisible();

    expect(c.getByText('Ważne')).toBeVisible();
    expect(canvasElement.querySelector('script')).toBeNull();

    const consent = within(c.getByRole('group', { name: 'Zgody' })).getByRole('checkbox');
    expect(consent).toHaveAccessibleName(/Zgoda na kontakt/);
    expect(c.getByText('Nieobsługiwany typ pola: FOO')).toBeVisible();
  },
};

export const SectionNested: Story = {
  args: {
    questions: [
      q(
        f('s1', 'SECTION', {
          title: 'Dane',
          repeatingSectionGrid: [q(f('n1', 'TEXT_FIELD', { title: 'Imię' }), 0)],
        }),
        0,
      ),
    ],
  },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByRole('heading', { level: 4, name: 'Dane' })).toBeVisible();
    expect(c.getByLabelText('Imię')).toBeVisible();
    const cell = c
      .getByRole('heading', { level: 4 })
      .closest('[style*="grid-area"]') as HTMLElement;
    expect(cell.style.gridArea).toBe('1 / 1 / span 1 / span 3');
  },
};

export const HiddenField: Story = {
  args: {
    questions: [
      q(f('a', 'TEXT_FIELD', { title: 'Widoczne' }), 0),
      q(f('b', 'TEXT_FIELD', { title: 'Ukryte' }), 1),
    ],
    hidden: new Set(['b']),
  },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByLabelText('Widoczne')).toBeVisible();
    expect(c.queryByLabelText('Ukryte')).toBeNull();
  },
};

export const SparseFields: Story = {
  args: {
    questions: [
      ...[
        'SECTION',
        'TEXT_FIELD',
        'NUMBER',
        'TEXTAREA',
        'RADIO',
        'SELECT',
        'CHECKBOX',
        'DATEPICKER',
        'FILE_UPLOADER',
        'TEXT_BLOCK',
        'CONSENT_SECTION',
      ].map((t, i) => q({ id: `s${i}`, type: t, techName: t } as FormField, i)),
    ],
  },
  play: async ({ canvasElement }) => {
    expect(canvasElement.querySelectorAll('app-field-host').length).toBe(11);
    expect(within(canvasElement).getByLabelText('TEXT FIELD')).toBeVisible(); // humanized techName fallback
  },
};

const stateTypes: Question[] = [
  f('kwota', 'NUMBER', { title: 'Kwota' }),
  f('opis', 'TEXTAREA', { title: 'Opis' }),
  f('data', 'DATEPICKER', { title: 'Data' }),
  f('sel', 'SELECT', { title: 'Wybór', options: opts }),
  f('teryt', 'SELECT', {
    title: 'Adres',
    dictionaryName: 'TERYT_4G_DOWODOWY',
    defaultValue: ['mazowieckie'],
  }),
  f('radio', 'RADIO', { title: 'W czyim imieniu', options: opts }),
  f('chk', 'CHECKBOX', { title: 'Zgoda ogólna' }),
  f('plik', 'FILE_UPLOADER', { title: 'Załącznik' }),
  f('zgody', 'CONSENT_SECTION', {
    title: undefined,
    consentSectionConfig: { consents: [{ description: 'Zgoda na kontakt', required: true }] },
  }),
].map((field, i) => q(field, i));

export const ZBledami: Story = {
  args: {
    questions: stateTypes,
    errors: new Map([
      ['kwota', 'Uzupełnij to pole'],
      ['opis', 'Uzupełnij to pole'],
      ['data', 'Uzupełnij to pole'],
      ['sel', 'Wybierz jedną z opcji'],
      ['teryt', 'Wybierz jedną z opcji'],
      ['radio', 'Wybierz jedną z opcji'],
      ['chk', 'Zaznacz to pole'],
      ['plik', 'Dodaj plik'],
      ['zgody', 'Zaznacz wymaganą zgodę'],
    ]),
  },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByLabelText('Kwota')).toHaveAccessibleDescription('Uzupełnij to pole');
    expect(c.getByLabelText('Kwota')).toBeInvalid();
    expect(c.getByRole('combobox', { name: 'Powiat' })).toHaveAccessibleDescription(
      'Wybierz jedną z opcji',
    );
    expect(c.getByRole('group', { name: 'W czyim imieniu' })).toHaveAccessibleDescription(
      'Wybierz jedną z opcji',
    );
    expect(c.getByRole('button', { name: 'Dodaj lub przeciągnij plik' })).toBeInvalid();
    expect(c.getByText('Zaznacz wymaganą zgodę')).toBeVisible();
  },
};

export const TylkoDoOdczytu: Story = {
  args: {
    questions: stateTypes,
    readOnly: new Set(stateTypes.map((x) => x.field.id)),
  },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByLabelText('Kwota')).toHaveAttribute('readonly');
    expect(c.getByLabelText('Opis')).toHaveAttribute('readonly');
    const sel = c.getByRole('combobox', { name: 'Wybór' });
    await userEvent.click(sel);
    expect(sel).toHaveAttribute('aria-expanded', 'false');
    for (const r of c.getAllByRole('radio')) expect(r).toBeDisabled();
    expect(c.getByRole('button', { name: 'Dodaj lub przeciągnij plik' })).toBeDisabled();
  },
};

export const ZPodpowiedzia: Story = {
  args: {
    questions: [
      f('pesel', 'TEXT_FIELD', { title: 'Numer PESEL', tooltipMessage: '<p>11 cyfr</p>' }),
      f('opis', 'TEXTAREA', { title: 'Opis', tooltipMessage: 'Krótko' }),
      f('radio', 'RADIO', { title: 'W czyim imieniu', options: opts, tooltipMessage: 'Pomoc' }),
      f('plik', 'FILE_UPLOADER', { title: 'Załącznik', tooltipMessage: 'Skan lub zdjęcie' }),
    ].map((field, i) => q(field, i)),
  },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const btn = c.getByRole('button', { name: 'Więcej informacji: Numer PESEL' });
    await userEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
    expect(c.getByText('11 cyfr')).toBeVisible();
    expect(c.getByRole('button', { name: 'Więcej informacji: W czyim imieniu' })).toBeVisible();
    expect(c.getByRole('button', { name: 'Więcej informacji: Załącznik' })).toBeVisible();
  },
};

export const ZRejestru: Story = {
  args: {
    questions: [
      f('pesel', 'TEXT_FIELD', {
        title: 'Numer PESEL',
        readOnly: true,
        defaultValueType: 'EXTERNAL_SYSTEM',
        defaultValue: 'PESEL.pesel',
        tooltipMessage: '11 cyfr',
      }),
      f('email', 'TEXT_FIELD', { title: 'E-mail', defaultValueType: 'EXTERNAL_SYSTEM' }),
      f('radio', 'RADIO', {
        title: 'Płeć',
        options: opts,
        defaultValueType: 'EXTERNAL_SYSTEM',
      }),
    ].map((field, i) => q(field, i)),
  },
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByLabelText(/Numer PESEL\s*, dane z rejestru/)).toHaveAttribute('readonly');
    expect(c.getByLabelText(/E-mail\s*, dane z rejestru/)).not.toHaveAttribute('readonly');
    expect(c.getByRole('group', { name: /^Płeć\s*, dane z rejestru$/ })).toBeVisible();
    expect(c.getAllByText('dane z rejestru')).toHaveLength(3);
  },
};
