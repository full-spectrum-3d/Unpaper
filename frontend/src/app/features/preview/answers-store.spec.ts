import { Component, inject, model, provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { FormDefinition, FormField } from './form-definition';
import { AnswersStore, initialAnswer } from './answers-store';
import { SAMPLE_REGISTRY_DATA } from './sample-registry-data';

const f = (p: Partial<FormField>): FormField => ({
  id: p.type ?? 'x',
  techName: 't',
  title: 'T',
  type: 'TEXT_FIELD',
  ...p,
});

describe('initialAnswer', () => {
  it('derives initial values by type', () => {
    expect(initialAnswer(f({ defaultValue: 'Urząd Gminy Ulan-Majorat' }))).toBe(
      'Urząd Gminy Ulan-Majorat',
    );
    expect(initialAnswer(f({ type: 'SELECT', defaultValue: ['Polska'] }))).toBe('Polska');
    expect(initialAnswer(f({ type: 'SELECT', defaultValue: [] }))).toBe('');
    const teryt = { type: 'SELECT', dictionaryName: 'TERYT_4G_DOWODOWY' };
    expect(initialAnswer(f({ ...teryt, defaultValue: [] }))).toEqual([]);
    expect(initialAnswer(f({ ...teryt, defaultValue: ['mazowieckie'] }))).toEqual(['mazowieckie']);
    expect(initialAnswer(f({ type: 'CHECKBOX' }))).toEqual([]);
    expect(
      initialAnswer(
        f({
          type: 'CONSENT_SECTION',
          consentSectionConfig: { consents: [{ description: 'a' }, { description: 'b' }] },
        }),
      ),
    ).toEqual([false, false]);
  });

  it('reads registry data for EXTERNAL_SYSTEM', () => {
    const field = f({ defaultValue: 'PESEL.name', defaultValueType: 'EXTERNAL_SYSTEM' });
    expect(initialAnswer(field)).toBe(SAMPLE_REGISTRY_DATA['PESEL.name']);
    expect(initialAnswer(f({ defaultValue: 'NOPE.x', defaultValueType: 'EXTERNAL_SYSTEM' }))).toBe(
      '',
    );
  });
});

describe('AnswersStore', () => {
  it('version increments on set and update', () => {
    const s = new AnswersStore();
    const sig = s.answer(f({}));
    const v = s.version();
    sig.set('a');
    expect(s.version()).toBe(v + 1);
    sig.update((x) => x + 'b');
    expect(sig()).toBe('ab');
    expect(s.version()).toBe(v + 2);
  });

  it('reset restores initial values', () => {
    const s = new AnswersStore();
    const field = f({ defaultValue: 'x' });
    const sig = s.answer(field);
    sig.set('changed');
    const v = s.version();
    s.reset();
    expect(sig()).toBe('x');
    expect(s.version()).toBeGreaterThan(v);
    expect(s.snapshot().get(field.id)).toBe('x');
  });

  it('answer returns same signal for same field', () => {
    const s = new AnswersStore();
    const field = f({});
    expect(s.answer(field)).toBe(s.answer(field));
  });
});

describe('AnswersStore.init', () => {
  const def = nadplata as unknown as FormDefinition;
  const page2 = def.tabs[1].questions[0].field;
  const nested = def.tabs[0].questions.find((q) => q.field.repeatingSectionGrid?.length)!.field
    .repeatingSectionGrid![0].field;

  it('snapshot is empty for never-initialised fields', () => {
    expect(new AnswersStore().snapshot().has(page2.id)).toBe(false);
  });

  it('creates entries for all fields incl. nested, bumping version once', () => {
    const s = new AnswersStore();
    s.init(def);
    expect(s.version()).toBe(1);
    expect(s.snapshot().get(page2.id)).toEqual(initialAnswer(page2));
    expect(s.snapshot().get(nested.id)).toEqual(initialAnswer(nested));
  });

  it('clears old entries when called with a new definition', () => {
    const s = new AnswersStore();
    s.init(def);
    s.init({ ...def, tabs: [] });
    expect(s.snapshot().size).toBe(0);
  });
});

@Component({ selector: 'app-child', template: '' })
class ChildComponent {
  readonly value = model<unknown>('');
}

@Component({
  imports: [ChildComponent],
  providers: [AnswersStore],
  template: '<app-child [(value)]="answer" />',
})
class HostComponent {
  readonly store = inject(AnswersStore);
  readonly answer = this.store.answer(f({ id: 'bound' }));
}

describe('AnswersStore two-way binding', () => {
  it('bumps version when a child model changes', () => {
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const { store } = fixture.componentInstance;
    const v = store.version();
    fixture.debugElement.children[0].componentInstance.value.set('x');
    expect(store.version()).toBe(v + 1);
    expect(store.snapshot().get('bound')).toBe('x');
  });
});
