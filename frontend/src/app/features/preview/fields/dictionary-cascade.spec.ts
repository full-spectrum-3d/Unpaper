import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AnswersStore } from '../answers-store';
import { findDictionary } from '../dictionaries.mock';
import { FormField } from '../form-definition';
import { FormState } from '../form-state';
import { cascadeLevels, DictionaryCascadeField } from './dictionary-cascade';

const teryt = findDictionary('TERYT_4G_DOWODOWY')!;

describe('cascadeLevels', () => {
  it('starts with the top level only', () => {
    const levels = cascadeLevels(teryt, []);
    expect(levels).toHaveLength(1);
    expect(levels[0].label).toBe('Województwo');
    expect(levels[0].options).toHaveLength(16);
  });

  it('adds the next level once a node with children is chosen', () => {
    const levels = cascadeLevels(teryt, ['mazowieckie']);
    expect(levels.map((l) => l.label)).toEqual(['Województwo', 'Powiat']);
    expect(levels[1].options.length).toBeGreaterThanOrEqual(2);
    expect(levels[1].options).toContain('Warszawa');
  });

  it('reaches all four levels on a full path', () => {
    const levels = cascadeLevels(teryt, ['mazowieckie', 'Warszawa', 'Warszawa', 'Warszawa']);
    expect(levels.map((l) => l.label)).toEqual(['Województwo', 'Powiat', 'Gmina', 'Miejscowość']);
  });

  it('ignores an unknown name', () => {
    expect(cascadeLevels(teryt, ['Atlantyda'])).toHaveLength(1);
  });
});

describe('DictionaryCascadeField', () => {
  let fixture: ComponentFixture<DictionaryCascadeField>;
  let store: AnswersStore;
  const el = () => fixture.nativeElement as HTMLElement;
  const field = (p: Partial<FormField> = {}): FormField => ({
    id: 'teryt',
    type: 'SELECT',
    techName: 'wojewodztwo',
    title: 'TERYT_4G_DOWODOWY',
    dictionaryName: 'TERYT_4G_DOWODOWY',
    ...p,
  });
  const create = async (f: FormField) => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), AnswersStore, FormState],
    });
    store = TestBed.inject(AnswersStore);
    fixture = TestBed.createComponent(DictionaryCascadeField);
    fixture.componentRef.setInput('field', f);
    await fixture.whenStable();
  };
  const inputs = () => [...el().querySelectorAll<HTMLInputElement>('input[role=combobox]')];
  const labels = () => [...el().querySelectorAll('label')].map((l) => l.textContent?.trim());
  const pick = async (index: number, option: string) => {
    inputs()[index].click();
    await fixture.whenStable();
    [...el().querySelectorAll<HTMLElement>('[role=option]')]
      .find((o) => o.textContent?.trim() === option)!
      .click();
    await fixture.whenStable();
  };

  it('exposes no technical group name when the title is hidden', async () => {
    await create(field());
    const group = el().querySelector('[role=group]')!;
    expect(group.hasAttribute('aria-label')).toBe(false);
    expect(group.hasAttribute('aria-labelledby')).toBe(false);
    expect(el().innerHTML).not.toContain('TERYT_4G_DOWODOWY');
  });

  it('reveals the next level after a choice', async () => {
    await create(field());
    expect(labels()).toEqual(['Województwo']);
    await pick(0, 'mazowieckie');
    expect(labels()).toEqual(['Województwo', 'Powiat']);
  });

  it('changing the top level drops the rest of the path', async () => {
    const f = field();
    await create(f);
    await pick(0, 'mazowieckie');
    await pick(1, 'Warszawa');
    await pick(2, 'Warszawa');
    await pick(3, 'Warszawa');
    expect(inputs()).toHaveLength(4);

    await pick(0, 'małopolskie');
    expect(store.answer(f)()).toEqual(['małopolskie']);
    expect(inputs()).toHaveLength(2);
    inputs()[1].click();
    await fixture.whenStable();
    const options = [...el().querySelectorAll('[role=option]')].map((o) => o.textContent?.trim());
    expect(options).toEqual(cascadeLevels(teryt, ['małopolskie'])[1].options);
  });

  it('hides a title that repeats the dictionary name', async () => {
    await create(field());
    expect(el().textContent).not.toContain('TERYT_4G_DOWODOWY');
  });

  it('uses a distinct title as the group legend', async () => {
    await create(field({ title: 'Adres w Polsce' }));
    const group = el().querySelector('[role=group]')!;
    const legend = el().querySelector('#' + group.getAttribute('aria-labelledby'))!;
    expect(legend.textContent).toContain('Adres w Polsce');
  });
});
