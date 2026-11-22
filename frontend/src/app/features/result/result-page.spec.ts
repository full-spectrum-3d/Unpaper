import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { provideStore } from '@ngrx/store';
import { MockStore, provideMockStore } from '@ngrx/store/testing';
import { ImportQueueActions } from '../../store/import-queue/import-queue.actions';
import {
  QueueItem,
  adapter,
  importQueueFeatureKey,
  importQueueReducer,
} from '../../store/import-queue/import-queue.reducer';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { mockReport } from '../import/mock-report';
import { ResultPage } from './result-page';

const done: QueueItem = {
  id: 'r1',
  name: 'wniosek.docx',
  size: 1,
  status: 'done',
  error: null,
  retryable: false,
  result: nadplata,
  report: mockReport(nadplata),
  startedAt: 0,
  durationMs: 1,
};

async function setup() {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      provideMockStore({
        initialState: { [importQueueFeatureKey]: { ids: ['r1'], entities: { r1: done } } },
      }),
    ],
  });
  const fixture = TestBed.createComponent(ResultPage);
  fixture.componentRef.setInput('id', 'r1');
  document.body.appendChild(fixture.nativeElement);
  await fixture.whenStable();
  const el: HTMLElement = fixture.nativeElement;
  const tab = (name: string) =>
    [...el.querySelectorAll<HTMLElement>('[role="tab"]')].find(
      (t) => t.textContent!.trim() === name,
    )!;
  const json = () => el.querySelector('app-json-view');
  return { fixture, el, tab, json };
}

describe('ResultPage', () => {
  beforeEach(() => (Element.prototype.scrollIntoView = vi.fn()));
  afterEach(() => {
    delete (Element.prototype as Partial<Element>).scrollIntoView;
    document.body.innerHTML = '';
  });

  it('renders the JSON view only while its tab is active', async () => {
    const { fixture, tab, json } = await setup();
    expect(tab('Podgląd formularza').getAttribute('aria-selected')).toBe('true');
    expect(json()).toBeNull();
    tab('JSON').click();
    await fixture.whenStable();
    expect(json()!.textContent).toBe(JSON.stringify(nadplata, null, 2));
    tab('Raport').click();
    await fixture.whenStable();
    expect(json()).toBeNull();
  });

  it('moves between tabs with arrow keys, Home and End, wrapping around', async () => {
    const { fixture, tab } = await setup();
    const key = async (from: string, k: string) => {
      tab(from).dispatchEvent(
        new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }),
      );
      await fixture.whenStable();
    };
    await key('Podgląd formularza', 'ArrowRight');
    expect(tab('JSON').getAttribute('aria-selected')).toBe('true');
    expect(document.activeElement).toBe(tab('JSON'));
    await key('JSON', 'End');
    expect(document.activeElement).toBe(tab('Edycja'));
    await key('Edycja', 'ArrowRight');
    expect(document.activeElement).toBe(tab('Podgląd formularza'));
    await key('Podgląd formularza', 'ArrowLeft');
    await key('Edycja', 'ArrowLeft');
    expect(tab('Raport').getAttribute('aria-selected')).toBe('true');
    expect(tab('Raport').getAttribute('tabindex')).toBe('0');
    expect(tab('JSON').getAttribute('tabindex')).toBe('-1');
    await key('Raport', 'Home');
    expect(document.activeElement).toBe(tab('Podgląd formularza'));
  });

  it('"Pokaż w JSON" switches to the JSON tab and focuses the highlighted fragment', async () => {
    const { fixture, el, tab } = await setup();
    tab('Raport').click();
    await fixture.whenStable();
    const link = el.querySelector<HTMLButtonElement>(
      '[aria-label="Pokaż w JSON: W07_CHOICE_OPTIONS"]',
    )!;
    link.click();
    await fixture.whenStable();
    expect(tab('JSON').getAttribute('aria-selected')).toBe('true');
    const fragment = el.querySelector(
      '[aria-label="Fragment JSON: tabs[0].questions[1].field.repeatingSectionGrid[0]"]',
    );
    expect(fragment).not.toBeNull();
    expect(document.activeElement).toBe(fragment);
  });

  it('dispatches edits from the Edycja tab and stays on it when the result changes', async () => {
    const { fixture, el, tab } = await setup();
    const store = TestBed.inject(MockStore);
    const dispatch = vi.spyOn(store, 'dispatch');
    tab('Edycja').click();
    await fixture.whenStable();
    const panel = el.querySelector<HTMLElement>('#result-panel-edit')!;
    expect(panel.hidden).toBe(false);
    const select = panel.querySelector('select')!;
    select.value = 'TEXTAREA';
    select.dispatchEvent(new Event('change'));
    const action = dispatch.mock.calls[0][0] as unknown as ReturnType<
      typeof ImportQueueActions.resultEdited
    >;
    expect(action.type).toBe(ImportQueueActions.resultEdited.type);
    expect(action.id).toBe('r1');

    store.setState({
      [importQueueFeatureKey]: {
        ids: ['r1'],
        entities: { r1: { ...done, result: action.result, edited: true } },
      },
    });
    await fixture.whenStable();
    expect(tab('Edycja').getAttribute('aria-selected')).toBe('true');
    expect(el.textContent).toContain('Formularz zmieniony ręcznie — sprawdź go w walidatorze.');
    tab('JSON').click();
    await fixture.whenStable();
    expect(el.querySelector('app-json-view')!.textContent).toBe(
      JSON.stringify(action.result, null, 2),
    );
  });

  it('puts the file name in the document title', async () => {
    await setup();
    expect(TestBed.inject(Title).getTitle()).toBe('Wynik: wniosek.docx – Cyfryzacja formularzy');
  });
});

describe('ResultPage with the real queue store', () => {
  beforeEach(() => (Element.prototype.scrollIntoView = vi.fn()));
  afterEach(() => {
    delete (Element.prototype as Partial<Element>).scrollIntoView;
    document.body.innerHTML = '';
  });

  it('shows a field added in Edycja in the JSON and the preview', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideStore(
          { [importQueueFeatureKey]: importQueueReducer },
          {
            initialState: {
              [importQueueFeatureKey]: adapter.setAll([done], adapter.getInitialState()),
            },
          },
        ),
      ],
    });
    const fixture = TestBed.createComponent(ResultPage);
    fixture.componentRef.setInput('id', 'r1');
    document.body.appendChild(fixture.nativeElement);
    await fixture.whenStable();
    const el: HTMLElement = fixture.nativeElement;
    const tab = (name: string) =>
      [...el.querySelectorAll<HTMLElement>('[role="tab"]')].find(
        (t) => t.textContent!.trim() === name,
      )!;
    const button = (text: RegExp) =>
      [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) =>
        text.test(b.textContent!.trim()),
      )!;

    tab('Edycja').click();
    await fixture.whenStable();
    button(/^Dodaj pole/).click();
    await fixture.whenStable();
    const form = [...el.querySelectorAll('legend')]
      .find((l) => l.textContent!.startsWith('Nowe pole'))!
      .closest('fieldset')!;
    const label = [...form.querySelectorAll('input')].find((i) => i.type !== 'checkbox')!;
    label.value = 'Kwota testowa';
    label.dispatchEvent(new Event('input'));
    const type = form.querySelector('select')!;
    type.value = 'NUMBER';
    type.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    button(/^Dodaj$/).click();
    await fixture.whenStable();

    tab('JSON').click();
    await fixture.whenStable();
    const json = JSON.parse(el.querySelector('app-json-view')!.textContent!);
    const titles: string[] = [];
    const walk = (
      qs: { field: { title?: string; type: string; repeatingSectionGrid?: unknown[] } }[],
    ) =>
      qs.forEach(({ field }) => {
        if (field.title === 'Kwota testowa') titles.push(field.type);
        walk((field.repeatingSectionGrid ?? []) as never);
      });
    json.tabs.forEach((t: { questions: never }) => walk(t.questions));
    expect(titles).toEqual(['NUMBER']);

    tab('Podgląd formularza').click();
    await fixture.whenStable();
    expect(
      [...el.querySelectorAll('label')].some((l) => l.textContent!.includes('Kwota testowa')),
    ).toBe(true);
  });
});
