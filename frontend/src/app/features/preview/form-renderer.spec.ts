import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { FormDefinition } from './form-definition';
import { FormRenderer, VISIBILITY_EVALUATOR } from './form-renderer';
import { evaluateVisibility } from './visibility';

let impl: undefined | ((call: number) => Promise<ReadonlySet<string>> | undefined);
let calls = 0;
let settled = 0;
const evaluator: typeof evaluateVisibility = async (...args) => {
  const result = await (impl?.(++calls) ?? evaluateVisibility(...args));
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
        { provide: VISIBILITY_EVALUATOR, useValue: evaluator },
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
    let releaseStale!: (hidden: ReadonlySet<string>) => void;
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

    releaseStale(new Set()); // stale result would show "Dane innej osoby"
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
});
