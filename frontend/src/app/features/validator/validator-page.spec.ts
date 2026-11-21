import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ErrorHandler } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideMockStore } from '@ngrx/store/testing';
import { provideApiConfiguration } from '../../shared/api/api-configuration';
import { QueueItem, importQueueFeatureKey } from '../../store/import-queue/import-queue.reducer';
import { ValidatorPage } from './validator-page';

const URL = '/api/v1/forms/validate';

const row = (id: string, result: unknown): QueueItem => ({
  id,
  name: `${id}.docx`,
  size: 1,
  status: 'done',
  error: null,
  retryable: false,
  result,
  report: null,
  startedAt: 0,
  durationMs: 1,
});
const d1 = row('d1', { title: 'T', tabs: [] });
const d2 = row('d2', { title: 'Inny', tabs: [{ title: 'x' }] });

const FORM = { title: 'F', tabs: [{ title: 'A' }] };

describe('ValidatorPage', () => {
  afterEach(() => {
    delete (Element.prototype as Partial<Element>).scrollIntoView;
  });

  const setup = () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration(''),
        provideRouter([]),
        provideMockStore({
          initialState: { [importQueueFeatureKey]: { ids: ['d1', 'd2'], entities: { d1, d2 } } },
        }),
      ],
    });
    const fixture = TestBed.createComponent(ValidatorPage);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    const http = TestBed.inject(HttpTestingController);
    const field = () => el.querySelector<HTMLTextAreaElement>('textarea')!;
    const button = (name: string) =>
      [...el.querySelectorAll<HTMLButtonElement>('button')].find(
        (b) => (b.getAttribute('aria-label') ?? b.textContent!.trim()) === name,
      );
    const checkButton = () => el.querySelector<HTMLButtonElement>('button[data-check]')!;
    const type = (text: string) => {
      field().value = text;
      field().dispatchEvent(new Event('input'));
      fixture.detectChanges();
    };
    const check = () => {
      checkButton().click();
      fixture.detectChanges();
    };
    const text = () => el.textContent!.replace(/\s+/g, ' ');
    const role = (r: string) => el.querySelector<HTMLElement>(`[role="${r}"]`);
    return { fixture, el, http, field, button, checkButton, type, check, text, role };
  };

  it('disables Sprawdź for empty text', () => {
    const { checkButton, type } = setup();
    expect(checkButton().disabled).toBe(true);
    type('   ');
    expect(checkButton().disabled).toBe(true);
    type('{}');
    expect(checkButton().disabled).toBe(false);
  });

  it('reports a syntax error without a request and focuses the field', () => {
    const { el, http, field, type, check } = setup();
    type('{"a":');
    check();
    http.expectNone(URL);
    const msg = el.querySelector<HTMLElement>('#validator-input-error')!;
    expect(msg.textContent).toMatch(/^Niepoprawny JSON/);
    expect(field().getAttribute('aria-invalid')).toBe('true');
    expect(field().getAttribute('aria-describedby')).toBe('validator-input-error');
    expect(document.activeElement).toBe(field());
  });

  it('has the error and aria attributes in place when the field receives focus', () => {
    const { el, field, type, check } = setup();
    let seen: { invalid: string | null; text?: string } | undefined;
    field().addEventListener('focus', () => {
      const id = field().getAttribute('aria-describedby');
      seen = {
        invalid: field().getAttribute('aria-invalid'),
        text: id ? el.querySelector(`#${id}`)?.textContent ?? undefined : undefined,
      };
    });
    type('{"a":');
    check();
    expect(seen?.invalid).toBe('true');
    expect(seen?.text).toMatch(/^Niepoprawny JSON/);
  });

  it('posts the parsed object once and shows the pending state', () => {
    const { http, checkButton, type, check } = setup();
    type(JSON.stringify(FORM));
    check();
    const req = http.expectOne(URL);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(FORM);
    expect(checkButton().textContent!.trim()).toBe('Sprawdzanie…');
    expect(checkButton().disabled).toBe(true);
    check();
    http.expectNone(URL);
    req.flush({ valid: true, errors: [], warnings: [] });
    http.verify();
  });

  it('shows success and focuses the Wynik heading', () => {
    const { fixture, el, http, type, check, role } = setup();
    type(JSON.stringify(FORM));
    check();
    http.expectOne(URL).flush({ valid: true, errors: [], warnings: [] });
    fixture.detectChanges();
    expect(role('status')!.textContent).toContain('JSON spełnia reguły COI.');
    const h2 = el.querySelector('h2')!;
    expect(h2.textContent!.trim()).toBe('Wynik');
    expect(document.activeElement).toBe(h2);
  });

  it('lists errors and warnings with links only for existing paths', () => {
    const { fixture, el, http, button, type, check, text, role } = setup();
    Element.prototype.scrollIntoView = vi.fn();
    type(JSON.stringify(FORM));
    check();
    http.expectOne(URL).flush({
      valid: false,
      errors: [
        { code: 'R06_REQUIREDNESS', message: 'm', path: 'tabs[0]' },
        { code: 'R01_SCHEMA', message: 'n', path: 'nie.ma' },
      ],
      warnings: [{ code: 'W02_LABEL_TOO_LONG', message: 'w' }],
    });
    fixture.detectChanges();
    expect(role('status')!.textContent).toContain('Znaleziono 2 błędy i 1 ostrzeżenie.');
    expect(text()).toContain('Błędy (2)');
    expect(text()).toContain('Ostrzeżenia (1)');
    expect(button('Pokaż w JSON: R06_REQUIREDNESS')).toBeTruthy();
    expect(button('Pokaż w JSON: R01_SCHEMA')).toBeUndefined();
    expect(button('Pokaż w JSON: W02_LABEL_TOO_LONG')).toBeUndefined();
    expect(text()).toContain('nie.ma');
    button('Pokaż w JSON: R06_REQUIREDNESS')!.click();
    fixture.detectChanges();
    const fragment = el.querySelector('[aria-label="Fragment JSON: tabs[0]"]');
    expect(fragment).not.toBeNull();
    expect(document.activeElement).toBe(fragment);
  });

  it('tolerates malformed issue lists', () => {
    const { fixture, http, type, check, text } = setup();
    type(JSON.stringify(FORM));
    check();
    http.expectOne(URL).flush({ valid: false, errors: null, warnings: [null, { code: 5 }] });
    fixture.detectChanges();
    expect(text()).toContain('Błędy (0)');
    expect(text()).toContain('Brak');
    expect(text()).toContain('Ostrzeżenia (1)');
  });

  it('marks the result stale after editing and keeps the checked JSON', () => {
    const { fixture, el, http, type, check, text } = setup();
    type(JSON.stringify(FORM));
    check();
    http.expectOne(URL).flush({ valid: true, errors: [], warnings: [] });
    fixture.detectChanges();
    expect(text()).not.toContain('JSON zmieniono po sprawdzeniu.');
    type('{"inny": 1}');
    expect(text()).toContain('JSON zmieniono po sprawdzeniu. Sprawdź ponownie.');
    expect(el.querySelector('app-json-view')!.textContent).toBe(JSON.stringify(FORM, null, 2));
  });

  it('shows a dedicated message for 422 and toUserMessage otherwise, dropping the old result', () => {
    const { fixture, http, type, check, role } = setup();
    type(JSON.stringify(FORM));
    check();
    http.expectOne(URL).flush({ valid: true, errors: [], warnings: [] });
    fixture.detectChanges();
    check();
    http
      .expectOne(URL)
      .flush({ code: 'VALIDATION_ERROR' }, { status: 422, statusText: 'Unprocessable' });
    fixture.detectChanges();
    expect(role('alert')!.textContent).toContain('Serwer odrzucił JSON jako niepoprawny.');
    expect(role('status')).toBeNull();
    check();
    http.expectOne(URL).flush({ code: 'X', detail: 'd' }, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(role('alert')!.textContent!.trim()).toBe('d');
  });

  it('loads and checks the queue item from ?item, following item changes', () => {
    const { fixture, el, http, field, role } = setup();
    fixture.componentRef.setInput('item', 'd1');
    fixture.detectChanges();
    expect(field().value).toBe(JSON.stringify(d1.result, null, 2));
    const first = http.expectOne(URL);
    expect(first.request.body).toEqual(d1.result);
    first.flush({ valid: false, errors: [], warnings: [] });
    fixture.detectChanges();
    expect(el.querySelector('h2')).not.toBeNull();
    fixture.componentRef.setInput('item', 'd2');
    fixture.detectChanges();
    expect(el.querySelector('h2')).toBeNull();
    expect(role('alert')).toBeNull();
    expect(field().value).toBe(JSON.stringify(d2.result, null, 2));
    expect(http.expectOne(URL).request.body).toEqual(d2.result);
  });

  it('clears the previous http error when switching items', () => {
    const { fixture, http, role } = setup();
    fixture.componentRef.setInput('item', 'd1');
    fixture.detectChanges();
    http.expectOne(URL).flush('x', { status: 500, statusText: 'Err' });
    fixture.detectChanges();
    expect(role('alert')).not.toBeNull();
    fixture.componentRef.setInput('item', 'd2');
    fixture.detectChanges();
    expect(role('alert')).toBeNull();
    http.expectOne(URL);
  });

  it('does not throw for a done row without a result', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration(''),
        provideRouter([]),
        provideMockStore({
          initialState: {
            [importQueueFeatureKey]: { ids: ['u'], entities: { u: row('u', undefined) } },
          },
        }),
      ],
    });
    const fixture = TestBed.createComponent(ValidatorPage);
    fixture.componentRef.setInput('item', 'u');
    expect(() => fixture.detectChanges()).not.toThrow();
    expect(fixture.nativeElement.querySelector('textarea').value).toBe('');
  });

  it('explains a missing queue item without a request', () => {
    const { fixture, http, text } = setup();
    fixture.componentRef.setInput('item', 'nope');
    fixture.detectChanges();
    expect(text()).toContain('Nie znaleziono wyniku do sprawdzenia. Wklej JSON ręcznie.');
    http.expectNone(URL);
  });

  it('resets the screen when item changes to an unknown id', () => {
    const { fixture, el, http, field, text } = setup();
    fixture.componentRef.setInput('item', 'd1');
    fixture.detectChanges();
    http.expectOne(URL).flush({ valid: true, errors: [], warnings: [] });
    fixture.detectChanges();
    fixture.componentRef.setInput('item', 'd2');
    fixture.detectChanges();
    const pending = http.expectOne(URL);
    fixture.componentRef.setInput('item', 'nope');
    fixture.detectChanges();
    expect(pending.cancelled).toBe(true);
    expect(field().value).toBe('');
    expect(el.querySelector('h2')).toBeNull();
    expect(el.querySelector('app-json-view')).toBeNull();
    expect(text()).toContain('Nie znaleziono wyniku do sprawdzenia. Wklej JSON ręcznie.');
  });

  it('clears the missing-item notice and the input error on input', () => {
    const { fixture, field, type, check, text } = setup();
    fixture.componentRef.setInput('item', 'nope');
    fixture.detectChanges();
    type('{"a":');
    check();
    expect(field().getAttribute('aria-invalid')).toBe('true');
    expect(text()).not.toContain('Nie znaleziono wyniku');
    type('{"a": 1}');
    expect(field().getAttribute('aria-invalid')).toBeNull();
    expect(field().getAttribute('aria-describedby')).toBeNull();
  });

  it('cancels a running check when the page is destroyed', () => {
    const { fixture, http, type, check } = setup();
    const handleError = vi.spyOn(TestBed.inject(ErrorHandler), 'handleError');
    type(JSON.stringify(FORM));
    check();
    const req = http.expectOne(URL);
    fixture.destroy();
    // A late response must not touch the destroyed view (afterNextRender would raise NG0911).
    if (!req.cancelled) req.flush({ valid: true, errors: [], warnings: [] });
    expect(handleError).not.toHaveBeenCalled();
    expect(req.cancelled).toBe(true);
  });

  it('reads an uploaded .json file into the field and rejects a bad one', async () => {
    const { fixture, el, field, text } = setup();
    const input = el.querySelector<HTMLInputElement>('input[type="file"]')!;
    const upload = (file: File) => {
      Object.defineProperty(input, 'files', { value: [file], configurable: true });
      input.dispatchEvent(new Event('change'));
    };
    upload(new File(['{"a": 1}'], 'form.JSON'));
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(field().value).toBe('{"a": 1}');
    });
    upload(new File(['x'], 'form.pdf'));
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(text()).toContain('Wgraj plik .json do 5 MB.');
    });
    expect(document.activeElement).toBe(field());
    expect(field().getAttribute('aria-describedby')).toBe('validator-input-error');
  });
});
