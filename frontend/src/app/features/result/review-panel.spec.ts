import { TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { mockReport } from '../import/mock-report';
import { formatJson } from './json-lines';
import { asReport, fieldPaths } from './report';
import { ReviewPanel } from './review-panel';

const { ranges } = formatJson(nadplata);

function render(report: unknown, form: unknown = nadplata) {
  const fixture = TestBed.createComponent(ReviewPanel);
  fixture.componentRef.setInput('report', asReport(report));
  fixture.componentRef.setInput('ranges', ranges);
  fixture.componentRef.setInput('paths', fieldPaths(form));
  fixture.detectChanges();
  const el: HTMLElement = fixture.nativeElement;
  return { fixture, el, text: () => el.textContent!.replace(/\s+/g, ' ') };
}

const field = (over: Record<string, unknown> = {}) => ({
  techName: 'cel',
  title: 'Cel wydania',
  tab: 'Sprawa',
  section: 'Dane sprawy',
  origin: 'document',
  confidence: 0.4,
  level: 'low',
  reasons: [],
  ...over,
});

describe('ReviewPanel', () => {
  it('renders nothing for a report without confidence', () => {
    const { el } = render({ warnings: [] });
    expect(el.textContent!.trim()).toBe('');
  });

  it('shows the score, its level and the field counts', () => {
    const { text } = render(mockReport(nadplata));
    expect(text()).toContain('78% · średnia');
    expect(text()).toContain('2 pola odczytane z dokumentu');
    expect(text()).toContain('Do sprawdzenia (2)');
  });

  it('lists review items with messages and marks the field without a source', () => {
    const { text } = render(mockReport(nadplata));
    expect(text()).toContain('35% · ważne');
    expect(text()).toContain('Etykiety nie ma w treści dokumentu - pole mogło zostać dopisane.');
    expect(text()).toContain('Źródło: nie znaleziono w dokumencie');
    expect(text()).toContain('Cały formularz');
  });

  it('quotes the source block and places it on a miniature page', () => {
    const source = {
      page: 2,
      text: 'Cel wydania: …',
      box: { x: 0.5, y: 0.25, width: 0.25, height: 0.1 },
      pageAspect: 0.72,
    };
    const { el, text } = render({
      confidence: { score: 0.4, level: 'low', fieldsTotal: 1, fieldsFromDocument: 1, toReview: 1 },
      fields: [field({ source })],
      review: [
        {
          kind: 'field',
          level: 'low',
          techName: 'cel',
          title: 'Cel wydania',
          tab: 'Sprawa',
          messages: ['Słaby skan.'],
        },
      ],
    });
    expect(text()).toContain('Źródło: strona 2 dokumentu, „Cel wydania: …”');
    const page = el.querySelector<HTMLElement>('[role="img"]')!;
    expect(page.getAttribute('aria-label')).toBe('Położenie na stronie 2 dokumentu');
    expect([page.style.width, page.style.height]).toEqual(['72px', '100px']);
    const mark = page.firstElementChild as HTMLElement;
    expect([mark.style.left, mark.style.top, mark.style.width, mark.style.height]).toEqual([
      '36px',
      '25px',
      '18px',
      '10px',
    ]);
  });

  it('has no miniature when the document has no fixed pages', () => {
    const { el } = render({
      confidence: { score: 0.9, level: 'high', fieldsTotal: 1, fieldsFromDocument: 1, toReview: 0 },
      fields: [field({ level: 'high', confidence: 0.9, source: { page: 1, text: 'Cel wydania' } })],
      review: [],
    });
    expect(el.querySelector('[role="img"]')).toBeNull();
    expect(el.textContent).toContain('Brak. Każde pole z dokumentu ma w nim potwierdzenie.');
  });

  it('emits the JSON path of a field that exists in the result', () => {
    const { fixture, el } = render(mockReport(nadplata));
    const paths: string[] = [];
    fixture.componentInstance.showInJson.subscribe((p) => paths.push(p));
    const buttons = [...el.querySelectorAll<HTMLButtonElement>('button')];
    expect(buttons.length).toBeGreaterThan(0);
    buttons[0].click();
    expect(paths).toHaveLength(1);
    expect(ranges.has(paths[0])).toBe(true);
  });

  it('survives malformed entries', () => {
    const { text } = render({
      confidence: { score: 0.5, level: 'weird' },
      fields: [null, 'x', { techName: 5 }],
      review: [null, { kind: 'field', messages: 'nie lista' }],
    });
    expect(text()).toContain('50% · wysoka');
    expect(text()).toContain('Do sprawdzenia (1)');
  });
});
