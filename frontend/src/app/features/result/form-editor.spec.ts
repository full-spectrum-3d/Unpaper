import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormDefinition, FormField } from '../preview/form-definition';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { allQuestions, htmlToText } from './form-edit';
import { InitialDataCatalog } from './initial-data';
import { SelectDictionaries } from './select-dictionaries';
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
    expect(el.querySelectorAll('app-field-row > div > fieldset').length).toBe(
      fields(nadplata as FormDefinition).length,
    );
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

  it('moves a field with arrow keys on its drag handle and keeps focus there', async () => {
    const { fixture, el, row, status, last, emitted } = await setup();
    const imie = byName(nadplata as FormDefinition, 'imie');
    const handle = () => row('imie').querySelector<HTMLElement>('.drag-handle')!;
    const press = (key: string) =>
      handle().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
    press('ArrowUp');
    await fixture.whenStable();
    expect(emitted).toEqual([]);
    press('ArrowDown');
    await fixture.whenStable();
    const kids = el.querySelectorAll(`#edit-field-${byName(last(), 'twoje_dane').id} + ul > li`);
    expect([...kids].map((li) => li.querySelector('legend')!.textContent)).toEqual([
      expect.stringContaining('Nazwisko'),
      expect.stringContaining('Imię'),
      expect.stringContaining('PESEL'),
    ]);
    expect(status()).toBe('Przesunięto pole „Imię” w dół.');
    expect(document.activeElement).toBe(el.querySelector(`#edit-field-${imie.id} .drag-handle`));
  });

  it('drops a dragged field after the row it is released on, within its section only', async () => {
    const { fixture, el, row, status, last, emitted } = await setup();
    const fire = (target: Element, type: string, clientY = 0) => {
      const event = new Event(type, { bubbles: true, cancelable: true });
      Object.assign(event, { clientY });
      target.dispatchEvent(event);
      return event;
    };
    const li = (techName: string) => row(techName).closest('li')!;
    fire(row('imie').querySelector('.drag-handle')!, 'dragstart');
    await fixture.whenStable();
    expect(row('imie').firstElementChild!.classList).toContain('opacity-50');
    // A field of another section is not a drop target.
    expect(fire(li('nip'), 'dragover', 1).defaultPrevented).toBe(false);
    expect(fire(li('numer_pesel'), 'dragover', 1).defaultPrevented).toBe(true);
    await fixture.whenStable();
    expect(li('numer_pesel').classList).toContain('drop-after');
    fire(li('numer_pesel'), 'drop', 1);
    await fixture.whenStable();
    expect(emitted.length).toBe(1);
    const kids = el.querySelectorAll(`#edit-field-${byName(last(), 'twoje_dane').id} + ul > li`);
    expect([...kids].map((k) => k.querySelector('legend')!.textContent)).toEqual([
      expect.stringContaining('Nazwisko'),
      expect.stringContaining('PESEL'),
      expect.stringContaining('Imię'),
    ]);
    expect(status()).toBe('Przesunięto pole „Imię” na pozycję 3 z 3.');
    expect(el.querySelector('.drop-after, .opacity-50')).toBeNull();
  });

  it('folds and unfolds one section or all of them', async () => {
    const { fixture, el, row, button, status } = await setup();
    const sectionList = () =>
      el.querySelector(`#edit-field-${byName(nadplata as FormDefinition, 'twoje_dane').id} + ul`);
    const fold = (techName: string) =>
      row(techName).querySelector<HTMLButtonElement>('button.fold')!;
    expect(fold('twoje_dane').getAttribute('aria-expanded')).toBe('true');
    expect(row('nip').querySelector('button.fold')).toBeNull();

    fold('twoje_dane').click();
    await fixture.whenStable();
    expect(sectionList()).toBeNull();
    expect(row('twoje_dane').querySelector('input')).toBeNull();
    expect(row('twoje_dane').textContent).toContain('pól: 3');
    expect(fold('twoje_dane').getAttribute('aria-expanded')).toBe('false');
    expect(status()).toBe('');

    const unfoldAll = button(el, '▾ Rozwiń wszystkie');
    const foldAll = button(el, '▸ Zwiń wszystkie');
    foldAll.click();
    await fixture.whenStable();
    expect(row('nip')).toBeNull();
    expect(foldAll.disabled).toBe(true);

    unfoldAll.click();
    await fixture.whenStable();
    expect(sectionList()).not.toBeNull();
    expect(row('nip')).not.toBeNull();
    expect(unfoldAll.disabled).toBe(true);
  });

  it('adds a text block with its text and no label', async () => {
    const { fixture, button, row, last, status } = await setup();
    const sectionLi = row('dane_podmiotu').closest('li')!;
    button(sectionLi, 'Dodaj pole').click();
    await fixture.whenStable();
    const form = sectionLi.querySelector('form')!;
    const type = form.querySelector('select')!;
    type.value = 'TEXT_BLOCK';
    type.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(form.querySelector('input[type="checkbox"]')).toBeNull();
    expect(form.textContent).toContain('Tytuł (opcjonalnie)');
    button(form, 'Dodaj').click();
    await fixture.whenStable();
    const content = form.querySelector<HTMLTextAreaElement>('textarea')!;
    expect(content.getAttribute('aria-invalid')).toBe('true');
    expect(document.activeElement).toBe(content);
    content.value = 'Wypełnij drukowanymi literami.';
    content.dispatchEvent(new Event('input'));
    button(form, 'Dodaj').click();
    await fixture.whenStable();
    const added = byName(last(), 'blok_tekstu');
    expect(added.type).toBe('TEXT_BLOCK');
    expect(htmlToText(added.description)).toBe('Wypełnij drukowanymi literami.');
    expect(status()).toBe('Dodano pole „Blok tekstu”.');
  });

  it('offers only information sections on the finish page', async () => {
    const { fixture, button, row } = await setup();
    const finishLi = row('podglad_uzupelnionego_wniosku').closest('li')!;
    button(finishLi, 'Dodaj pole').click();
    await fixture.whenStable();
    const options = [...finishLi.querySelectorAll('form select option')].map((o) =>
      o.textContent!.trim(),
    );
    expect(options).toEqual(['Sekcja informacyjna']);
    const typeSelect = row('podglad_1').querySelector('select')!;
    expect([...typeSelect.options].map((o) => o.value)).toEqual(['TEXT_BLOCK', 'INFO_SECTION']);
  });

  it('switches a list to a predefined dictionary', async () => {
    TestBed.configureTestingModule({
      providers: [
        {
          provide: SelectDictionaries,
          useValue: {
            list: signal([{ name: 'Kraje', description: 'Lista państw', multiLevelTree: false }]),
          },
        },
      ],
    });
    const { fixture, row, last, status } = await setup();
    const type = row('nip').querySelector('select')!;
    type.value = 'SELECT';
    type.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const source = row('nip').querySelectorAll('select')[1];
    expect([...source.options].map((o) => o.textContent!.trim())).toEqual([
      'Własne opcje',
      'Słownik: Kraje',
    ]);
    source.value = 'Kraje';
    source.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'nip')).toMatchObject({ dictionaryName: 'Kraje', options: [] });
    expect(status()).toBe('Pole „NIP” bierze teraz opcje ze słownika Kraje.');
    expect(row('nip').querySelector('textarea[id$="-options"]')).toBeNull();
    expect(row('nip').textContent).toContain('Lista państw');
  });

  it('edits the consents of a consent section', async () => {
    const { fixture, row, button, last, emitted } = await setup();
    const zgoda = row('zgoda');
    button(zgoda, '+ Dodaj zgodę').click();
    await fixture.whenStable();
    const second = zgoda.querySelectorAll<HTMLTextAreaElement>('app-consents-editor textarea')[1];
    expect(document.activeElement).toBe(second);
    second.value = '  ';
    second.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(second.getAttribute('aria-invalid')).toBe('true');
    expect(emitted).toEqual([]);
    second.value = 'Oświadczam, że dane są prawdziwe.';
    second.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const consents = byName(last(), 'zgoda').consentSectionConfig!.consents;
    expect(consents.length).toBe(2);
    expect(consents[0]).toEqual(
      byName(nadplata as FormDefinition, 'zgoda').consentSectionConfig!.consents[0],
    );
    expect(htmlToText(consents[1].description)).toBe('Oświadczam, że dane są prawdziwe.');
  });

  it('sets and clears the validator of a text field', async () => {
    const { fixture, row, last, status } = await setup();
    const format = () => row('nip').querySelector<HTMLSelectElement>('select[id$="-format"]')!;
    expect(format().value).toBe('NIP');
    expect(row('nip').querySelector('legend')!.textContent).toContain('NIP');
    format().value = 'REGON';
    format().dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'nip').validation).toEqual(['REQUIRED', 'REGON']);
    expect(status()).toBe('Pole „NIP” ma teraz walidator REGON.');
    format().value = '';
    format().dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'nip').validation).toEqual(['REQUIRED']);
    expect(status()).toBe('Usunięto walidator pola „NIP”.');
    // Only text fields take format validators.
    const type = row('nip').querySelector('select')!;
    type.value = 'NUMBER';
    type.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(format()).toBeNull();
  });

  it('edits initial-data fields; a not editable attribute keeps the field read-only', async () => {
    TestBed.configureTestingModule({
      providers: [
        {
          provide: InitialDataCatalog,
          useValue: {
            sources: signal([
              {
                source: 'PESEL',
                name: 'Rejestr PESEL',
                attributes: [
                  {
                    attribute: 'name',
                    ref: 'PESEL.name',
                    label: 'Imię',
                    fieldType: 'TEXT_FIELD',
                    editable: false,
                  },
                ],
              },
              {
                source: 'MLPZ',
                name: 'Dane zalogowanego użytkownika',
                attributes: [
                  {
                    attribute: 'email',
                    ref: 'MLPZ.email',
                    label: 'E-mail',
                    fieldType: 'TEXT_FIELD',
                    editable: true,
                  },
                ],
              },
            ]),
          },
        },
      ],
    });
    const { fixture, row, last, status } = await setup();
    const imie = row('imie');
    expect(imie.querySelector('legend')!.textContent).toContain('dane inicjalne');
    expect(imie.querySelector<HTMLInputElement>('app-text-field input')!.value).toBe('Imię');
    const readOnly = [
      ...imie.querySelectorAll<HTMLInputElement>('details input[type="checkbox"]'),
    ][0];
    expect(readOnly.checked).toBe(true);
    expect(readOnly.disabled).toBe(true);
    const initial = imie.querySelector<HTMLSelectElement>('select[id$="-initial"]')!;
    expect(initial.value).toBe('PESEL.name');
    initial.value = 'MLPZ.email';
    initial.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'imie')).toMatchObject({
      defaultValue: 'MLPZ.email',
      defaultValueType: 'EXTERNAL_SYSTEM',
    });
    expect(status()).toBe('Pole „Imię” pobiera teraz dane inicjalne MLPZ.email.');
    expect(
      row('imie').querySelector<HTMLInputElement>('details input[type="checkbox"]')!.disabled,
    ).toBe(false);
  });

  it('renames a techName and fixes the conditions that refer to it', async () => {
    const { fixture, row, last, status } = await setup();
    const input = [
      ...row('kraj').querySelectorAll<HTMLInputElement>('details app-text-field input'),
    ][0];
    input.value = 'Zły znak!';
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await fixture.whenStable();
    expect(input.getAttribute('aria-invalid')).toBe('true');
    input.value = 'ulica';
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await fixture.whenStable();
    expect(row('kraj').textContent).toContain('Ta nazwa techniczna jest już użyta');
    input.value = 'panstwo';
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await fixture.whenStable();
    expect(fields(last()).some((f) => f.techName === 'kraj')).toBe(false);
    expect(byName(last(), 'ulica').states![0].query).toContain("'panstwo' in field.techName");
    expect(status()).toBe('Zmieniono nazwę techniczną pola „Kraj” na panstwo.');
  });

  it('edits description, list search and dynamic states', async () => {
    const { fixture, row, button, last, emitted } = await setup();
    const description = row('nip').querySelector<HTMLTextAreaElement>(
      'textarea[id$="-description"]',
    )!;
    description.value = 'Numer z 10 cyfr.';
    description.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(htmlToText(byName(last(), 'nip').description)).toBe('Numer z 10 cyfr.');

    const states = row('nip').querySelector('app-states-editor')!;
    button(states as HTMLElement, '+ Dodaj stan').click();
    await fixture.whenStable();
    const query = states.querySelector<HTMLTextAreaElement>('textarea')!;
    expect(document.activeElement).toBe(query);
    const before = emitted.length;
    query.value = '"Tak" in (';
    query.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(query.getAttribute('aria-invalid')).toBe('true');
    expect(states.textContent).toContain('Błąd składni JSONata');
    expect(emitted.length).toBe(before);
    query.value = '$exists(nazwa)';
    query.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'nip').states).toEqual([{ type: 'SHOW', query: '$exists(nazwa)' }]);
    const type = row('nip').querySelector<HTMLSelectElement>('app-states-editor select')!;
    type.value = 'READ_ONLY';
    type.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'nip').states).toEqual([{ type: 'READ_ONLY', query: '$exists(nazwa)' }]);
    // Sections take only SHOW.
    const sectionTypes = row('dane_podmiotu').querySelector<HTMLSelectElement>(
      'app-states-editor select',
    )!;
    expect([...sectionTypes.options].map((o) => o.value)).toEqual(['SHOW']);
  });

  it('sets a fixed default value of a text field and a list', async () => {
    const { fixture, row, last } = await setup();
    const mode = row('nazwa').querySelector<HTMLSelectElement>('select[id$="-default"]')!;
    expect([...mode.options].map((o) => o.textContent!.trim())).toEqual([
      'Brak',
      'Stała wartość',
      'Dane inicjalne',
    ]);
    mode.value = 'value';
    mode.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const value = [
      ...row('nazwa').querySelectorAll<HTMLInputElement>('details app-text-field input'),
    ][1];
    value.value = 'Firma sp. z o.o.';
    value.dispatchEvent(new Event('change', { bubbles: true }));
    await fixture.whenStable();
    expect(byName(last(), 'nazwa').defaultValue).toBe('Firma sp. z o.o.');
    // A list without initial data offers no "Dane inicjalne".
    const listMode = row('kraj').querySelector<HTMLSelectElement>('select[id$="-default"]')!;
    expect([...listMode.options].map((o) => o.value)).toEqual(['none', 'value']);
    expect(listMode.value).toBe('value');
  });

  it('sets the requiredness and the files of a consent section', async () => {
    const { fixture, row, last, status } = await setup();
    const required = [...row('zgoda').querySelectorAll('label')]
      .find((l) => l.textContent!.includes('Zgody wymagane'))!
      .querySelector('input')!;
    const before = !!byName(nadplata as FormDefinition, 'zgoda').consentSectionConfig!.required;
    expect(required.checked).toBe(before);
    required.click();
    await fixture.whenStable();
    expect(byName(last(), 'zgoda').consentSectionConfig!.required).toBe(!before);
    const files = row('zgoda').querySelector<HTMLTextAreaElement>('textarea[id$="-files"]')!;
    files.value = 'klauzula.pdf\n\nregulamin.pdf';
    files.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(byName(last(), 'zgoda').consentSectionConfig!.files).toEqual([
      'klauzula.pdf',
      'regulamin.pdf',
    ]);
    expect(status()).toBe('Zmieniono pliki zgody w polu „Sekcja zgód”.');
  });
});
