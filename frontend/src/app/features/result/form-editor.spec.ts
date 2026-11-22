import { TestBed } from '@angular/core/testing';
import { FormDefinition, FormField } from '../preview/form-definition';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { allQuestions } from './form-edit';
import { FormEditor } from './form-editor';

const fields = (d: FormDefinition): FormField[] =>
  d.tabs.flatMap((t) => [...allQuestions(t.questions)].map((q) => q.field));
const byName = (d: FormDefinition, techName: string) =>
  fields(d).find((f) => f.techName === techName)!;

async function setup() {
  const fixture = TestBed.createComponent(FormEditor);
  const emitted: FormDefinition[] = [];
  fixture.componentRef.setInput('definition', nadplata);
  // Plays the store: each edit comes back as the new input.
  fixture.componentInstance.edited.subscribe((d) => {
    emitted.push(d);
    fixture.componentRef.setInput('definition', d);
  });
  document.body.appendChild(fixture.nativeElement);
  await fixture.whenStable();
  const el: HTMLElement = fixture.nativeElement;
  const row = (techName: string) =>
    el.querySelector<HTMLElement>(
      `#edit-field-${byName(nadplata as FormDefinition, techName).id}`,
    )!;
  const button = (root: HTMLElement, text: string) =>
    [...root.querySelectorAll('button')].find((b) => b.textContent!.trim().startsWith(text))!;
  const status = () => el.querySelector('[role="status"]')!.textContent!.trim();
  return { fixture, el, emitted, row, button, status, last: () => emitted.at(-1)! };
}

describe('FormEditor', () => {
  afterEach(() => (document.body.innerHTML = ''));

  it('lists pages as headings with every field in a labelled fieldset', async () => {
    const { el } = await setup();
    const headings = [...el.querySelectorAll('h2')].map((h) => h.textContent!.trim());
    expect(headings[0]).toBe('Strona 1: Dane');
    expect(el.querySelectorAll('fieldset').length).toBe(fields(nadplata as FormDefinition).length);
    for (const input of el.querySelectorAll<HTMLInputElement>('input, select, textarea')) {
      expect(input.labels?.length || input.closest('label')).toBeTruthy();
    }
  });

  it('adds a field to a section and focuses its label input', async () => {
    const { fixture, el, button, row, last, status } = await setup();
    const section = row('dane_podmiotu').closest('li')!;
    button(section, 'Dodaj pole').click();
    await fixture.whenStable();
    const form = section.querySelector('form')!;
    const label = form.querySelector('input')!;
    expect(document.activeElement).toBe(label);
    label.value = 'Liczba pracowników';
    label.dispatchEvent(new Event('input'));
    const type = form.querySelector('select')!;
    type.value = 'NUMBER';
    type.dispatchEvent(new Event('change'));
    form.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click();
    await fixture.whenStable();
    button(form, 'Dodaj').click();
    await fixture.whenStable();
    const added = byName(last(), 'liczba_pracownikow');
    expect(added).toMatchObject({ type: 'NUMBER', validation: ['REQUIRED'] });
    expect(status()).toBe('Dodano pole „Liczba pracowników”.');
    expect(document.activeElement).toBe(el.querySelector(`#edit-field-${added.id} input`));
  });

  it('shows an error for an empty label instead of adding', async () => {
    const { fixture, emitted, button, row } = await setup();
    const section = row('dane_podmiotu').closest('li')!;
    button(section, 'Dodaj pole').click();
    await fixture.whenStable();
    button(section.querySelector('form')!, 'Dodaj').click();
    await fixture.whenStable();
    const label = section.querySelector('form input')!;
    expect(label.getAttribute('aria-invalid')).toBe('true');
    const error = document.getElementById(label.getAttribute('aria-describedby')!)!;
    expect(error.textContent).toContain('Podaj etykietę pola.');
    expect(emitted).toEqual([]);
  });

  it('rejects an emptied label of an existing field', async () => {
    const { fixture, emitted, row } = await setup();
    const input = row('nip').querySelector('input')!;
    input.value = '  ';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await fixture.whenStable();
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(emitted).toEqual([]);
  });

  it('changes the type and announces it', async () => {
    const { fixture, row, last, status } = await setup();
    const select = row('nip').querySelector('select')!;
    select.value = 'NUMBER';
    select.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'nip')).toMatchObject({ type: 'NUMBER', validation: ['REQUIRED'] });
    expect(status()).toBe('Zmieniono typ pola „NIP” na Liczba.');
    // The row stays (same field id), so focus is not lost.
    expect(row('nip').querySelector('select')!.value).toBe('NUMBER');
  });

  it('removes a field only after confirmation and moves focus to the next row', async () => {
    const { fixture, row, button, emitted, last, status } = await setup();
    const nazwa = row('nazwa');
    button(nazwa, 'Usuń').click();
    await fixture.whenStable();
    expect(emitted).toEqual([]);
    const confirm = button(nazwa, 'Tak, usuń');
    expect(document.activeElement).toBe(confirm);
    button(nazwa, 'Anuluj').click();
    await fixture.whenStable();
    expect(document.activeElement).toBe(button(nazwa, 'Usuń'));

    button(nazwa, 'Usuń').click();
    await fixture.whenStable();
    button(nazwa, 'Tak, usuń').click();
    await fixture.whenStable();
    expect(fields(last()).some((f) => f.techName === 'nazwa')).toBe(false);
    expect(status()).toBe('Usunięto pole „Nazwa”.');
    expect(document.activeElement).toBe(row('nip').querySelector('input'));
  });

  it('tells which visibility conditions were dropped with a removed field', async () => {
    const { fixture, row, button, status } = await setup();
    const podmiot = row('podmiot_wniosku');
    button(podmiot, 'Usuń').click();
    await fixture.whenStable();
    button(podmiot, 'Tak, usuń').click();
    await fixture.whenStable();
    expect(status()).toContain('Usunięto warunek widoczności: „Dane podmiotu”');
  });

  it('moves a field down and keeps focus on its arrow until it reaches the end', async () => {
    const { fixture, el, row, button, status, last } = await setup();
    const imie = byName(nadplata as FormDefinition, 'imie');
    expect(button(row('imie'), '↑').disabled).toBe(true);
    button(row('imie'), '↓').click();
    await fixture.whenStable();
    const kids = el.querySelectorAll(`#edit-field-${byName(last(), 'twoje_dane').id} + ul > li`);
    expect([...kids].map((li) => li.querySelector('legend')!.textContent)).toEqual([
      expect.stringContaining('Nazwisko'),
      expect.stringContaining('Imię'),
      expect.stringContaining('PESEL'),
    ]);
    expect(status()).toBe('Przesunięto pole „Imię” w dół.');
    expect(document.activeElement).toBe(
      el.querySelector(`#edit-field-${imie.id} button.move-down`),
    );
    button(row('imie'), '↓').click();
    await fixture.whenStable();
    expect(document.activeElement).toBe(el.querySelector(`#edit-field-${imie.id} button.move-up`));
  });

  it('shows registry fields without edit controls', async () => {
    const { row } = await setup();
    expect(row('imie').textContent).toContain('Dane z rejestru');
    expect(row('imie').querySelector('select')).toBeNull();
  });
});
