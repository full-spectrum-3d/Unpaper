import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Combobox } from './combobox';

@Component({
  imports: [Combobox],
  template: `
    <app-combobox label="Kraj" [options]="options" [(value)]="first">
      <small description>Opis pola</small>
    </app-combobox>
    <app-combobox label="Kraj 2" [options]="options" [searchable]="true" [(value)]="second" />
  `,
})
class Host {
  readonly options = ['Polska', 'Niemcy', 'Norwegia'];
  readonly first = signal('');
  readonly second = signal('');
}

describe('Combobox', () => {
  let fixture: ComponentFixture<Host>;
  let host: Host;
  let inputs: HTMLInputElement[];

  const render = async () => {
    fixture.detectChanges();
    await fixture.whenStable();
  };
  const key = async (el: HTMLElement, k: string) => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
    await render();
  };
  const type = async (el: HTMLInputElement, text: string) => {
    el.focus();
    el.value = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    await render();
  };
  const options = () =>
    [...fixture.nativeElement.querySelectorAll('[role="option"]')] as HTMLElement[];

  beforeEach(async () => {
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(Host);
    host = fixture.componentInstance;
    await render();
    inputs = [...fixture.nativeElement.querySelectorAll('input')];
  });

  it('renders a labelled, collapsed combobox with placeholder', () => {
    const [input] = inputs;
    expect(input.getAttribute('role')).toBe('combobox');
    expect(input.getAttribute('aria-expanded')).toBe('false');
    const label = fixture.nativeElement.querySelector('label') as HTMLLabelElement;
    expect(label.htmlFor).toBe(input.id);
    expect(input.id).toMatch(/^app-combobox-\d+$/);
    expect(input.placeholder).toBe('Wybierz');
    expect(input.value).toBe('');
  });

  it('navigates with the keyboard and selects with Enter', async () => {
    const [input] = inputs;
    await key(input, 'ArrowDown');
    expect(input.getAttribute('aria-expanded')).toBe('true');
    const listbox = fixture.nativeElement.querySelector('[role="listbox"]') as HTMLElement;
    expect(input.getAttribute('aria-controls')).toBe(listbox.id);
    expect(options().length).toBe(3);
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[0].id);
    await key(input, 'ArrowDown');
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[1].id);
    await key(input, 'End');
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[2].id);
    await key(input, 'Home');
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[0].id);
    await key(input, 'ArrowDown');
    await key(input, 'Enter');
    expect(host.first()).toBe('Niemcy');
    expect(input.getAttribute('aria-expanded')).toBe('false');
    expect(input.value).toBe('Niemcy');
  });

  it('closes with Escape without changing the value', async () => {
    const [input] = inputs;
    await key(input, 'ArrowDown');
    await key(input, 'ArrowDown');
    await key(input, 'Escape');
    expect(input.getAttribute('aria-expanded')).toBe('false');
    expect(host.first()).toBe('');
  });

  it('filters options when searchable', async () => {
    const search = inputs[1];
    expect(search.getAttribute('aria-autocomplete')).toBe('list');
    await type(search, 'nor');
    expect(options().map((o) => o.textContent?.trim())).toEqual(['Norwegia']);
    await type(search, 'xyz');
    expect(options().length).toBe(0);
    expect(fixture.nativeElement.textContent).toContain('Brak wyników');
  });

  it('announces empty results in a persistent status region', async () => {
    const search = inputs[1];
    const status = () =>
      search.parentElement!.querySelector('[role="status"]') as HTMLElement | null;
    const before = status();
    expect(before).not.toBeNull();
    expect(before!.textContent?.trim()).toBe('');
    await type(search, 'xyz');
    expect(status()).toBe(before);
    expect(before!.textContent?.trim()).toBe('Brak wyników');
  });

  it('restores the value on blur without committing the query', async () => {
    host.second.set('Polska');
    await render();
    const search = inputs[1];
    await type(search, 'nor');
    search.dispatchEvent(new FocusEvent('blur'));
    await render();
    expect(host.second()).toBe('Polska');
    expect(search.value).toBe('Polska');
    expect(search.getAttribute('aria-expanded')).toBe('false');
  });

  it('is readonly without aria-autocomplete when not searchable', () => {
    expect(inputs[0].readOnly).toBe(true);
    expect(inputs[0].hasAttribute('aria-autocomplete')).toBe(false);
  });

  it('clears the value with the clear button', async () => {
    const clearButton = () =>
      fixture.nativeElement.querySelector(
        'button[aria-label="Wyczyść: Kraj"]',
      ) as HTMLButtonElement | null;
    expect(clearButton()).toBeNull();
    host.first.set('Polska');
    await render();
    clearButton()!.click();
    await render();
    expect(host.first()).toBe('');
    expect(document.activeElement).toBe(inputs[0]);
    expect(clearButton()).toBeNull();
  });

  it('marks the selected option', async () => {
    host.first.set('Norwegia');
    await render();
    await key(inputs[0], 'ArrowDown');
    expect(options().map((o) => o.getAttribute('aria-selected'))).toEqual([
      'false',
      'false',
      'true',
    ]);
  });

  it('gives each instance unique ids and closes on outside pointerdown', async () => {
    const [a, b] = inputs;
    expect(a.id).not.toBe(b.id);
    await key(a, 'ArrowDown');
    await key(b, 'ArrowDown');
    const ids = [...fixture.nativeElement.querySelectorAll('[role="listbox"]')].map(
      (l: Element) => l.id,
    );
    expect(new Set(ids).size).toBe(2);
    b.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    b.click();
    await render();
    expect(a.getAttribute('aria-expanded')).toBe('false');
    expect(b.getAttribute('aria-expanded')).toBe('true');
  });

  it('selects an option on click', async () => {
    inputs[0].click();
    await render();
    options()[2].click();
    await render();
    expect(host.first()).toBe('Norwegia');
    expect(inputs[0].getAttribute('aria-expanded')).toBe('false');
  });

  it('prevents default on pointerdown anywhere in the listbox (scrollbar drag keeps focus)', async () => {
    inputs[0].click();
    await render();
    const listbox = fixture.nativeElement.querySelector('[role="listbox"]') as HTMLElement;
    const ev = new PointerEvent('pointerdown', { bubbles: true, cancelable: true });
    listbox.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
    options()[1].click();
    await render();
    expect(host.first()).toBe('Niemcy');
  });

  it('renders the description slot between label and input', () => {
    const root = fixture.nativeElement.querySelector('app-combobox') as HTMLElement;
    const label = root.querySelector('label')!;
    const description = root.querySelector('[description]')!;
    const input = root.querySelector('input')!;
    expect(
      label.compareDocumentPosition(description) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      description.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
