import { Component, signal, viewChild } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { formatJson } from './json-lines';
import { JsonView } from './json-view';

@Component({
  imports: [JsonView],
  template: `<app-json-view [lines]="lines" [highlight]="highlight()" label="Test JSON" />`,
})
class Host {
  readonly lines = formatJson(nadplata);
  readonly highlight = signal<string | null>(null);
  readonly view = viewChild.required(JsonView);
}

describe('JsonView', () => {
  afterEach(() => {
    delete (Element.prototype as Partial<Element>).scrollIntoView;
  });

  const setup = () => {
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    const region = () => el.querySelector<HTMLElement>('[role="region"]')!;
    const fragments = () => [...el.querySelectorAll<HTMLElement>('.bg-warning-subtle')];
    const range = (f: HTMLElement) => [...f.querySelectorAll('[data-line]')].map((l) => Number(l.getAttribute('data-line')));
    return { fixture, host: fixture.componentInstance, region, fragments, range };
  };

  it('renders the exact stringified JSON in a labelled region, with and without highlight', () => {
    const { fixture, host, region } = setup();
    expect(region().getAttribute('aria-label')).toBe('Test JSON');
    expect(region().textContent).toBe(JSON.stringify(nadplata, null, 2));
    host.highlight.set('tabs[0]');
    fixture.detectChanges();
    expect(region().textContent).toBe(JSON.stringify(nadplata, null, 2));
  });

  it('highlights exactly one fragment and follows highlight changes', () => {
    const { fixture, host, fragments, range } = setup();
    const { ranges } = host.lines;
    const expected = (p: string) => {
      const { start, end } = ranges.get(p)!;
      return Array.from({ length: end - start + 1 }, (_, i) => start + i);
    };
    host.highlight.set('tabs[0]');
    fixture.detectChanges();
    expect(fragments().length).toBe(1);
    expect(fragments()[0].getAttribute('role')).toBe('group');
    expect(fragments()[0].getAttribute('aria-label')).toBe('Fragment JSON: tabs[0]');
    expect(range(fragments()[0])).toEqual(expected('tabs[0]'));
    host.highlight.set('title');
    fixture.detectChanges();
    expect(fragments().length).toBe(1);
    expect(range(fragments()[0])).toEqual(expected('title'));
    host.highlight.set('no.such.path');
    fixture.detectChanges();
    expect(fragments().length).toBe(0);
  });

  it('reveal() focuses the fragment and scrolls its first line to the centre', () => {
    const { fixture, host, fragments } = setup();
    // jsdom does not implement scrollIntoView.
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    host.highlight.set('tabs[0]');
    fixture.detectChanges();
    host.view().reveal();
    fixture.detectChanges();
    const first = fragments()[0].querySelector('[data-line]');
    expect(document.activeElement).toBe(fragments()[0]);
    expect(scroll).toHaveBeenCalledTimes(1);
    expect(scroll.mock.contexts[0]).toBe(first);
    expect(scroll).toHaveBeenCalledWith({ block: 'center' });
  });
});
