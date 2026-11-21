import { TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { mockReport } from '../import/mock-report';
import { formatJson } from './json-lines';
import { asReport, ConversionReport } from './report';
import { ReportView } from './report-view';

const { ranges } = formatJson(nadplata);

function render(report: unknown) {
  const fixture = TestBed.createComponent(ReportView);
  fixture.componentRef.setInput('report', asReport(report));
  fixture.componentRef.setInput('ranges', ranges);
  fixture.detectChanges();
  const el: HTMLElement = fixture.nativeElement;
  return { fixture, el, text: () => el.textContent!.replace(/\s+/g, ' ') };
}

describe('ReportView', () => {
  it('shows sections in order with counts', () => {
    const { el } = render(mockReport(nadplata));
    expect([...el.querySelectorAll('h2')].map((h) => h.textContent!.trim())).toEqual([
      'Ostrzeżenia (3)',
      'Poprawki autonaprawy (1)',
      'Propozycje słowników (1)',
      'Statystyki',
      'Przetwarzanie',
    ]);
  });

  it('emits the path from the show-in-JSON button of a linkable issue', () => {
    const { fixture, el } = render(mockReport(nadplata));
    const paths: string[] = [];
    fixture.componentInstance.showInJson.subscribe((p) => paths.push(p));
    const btn = el.querySelector<HTMLButtonElement>('button[aria-label="Pokaż w JSON: W07_CHOICE_OPTIONS"]')!;
    expect(btn.textContent!.trim()).toBe('Pokaż w JSON');
    btn.click();
    expect(paths).toEqual(['tabs[0].questions[1]']);
  });

  it('marks draft paths without a button', () => {
    const { el, text } = render(mockReport(nadplata));
    expect(text()).toContain('subject_pages[0].sections[0].fields[0] (miejsce w szkicu, nie w wyniku)');
    expect(el.querySelector('button[aria-label="Pokaż w JSON: W03_UNPLACED_FIELD"]')).toBeNull();
  });

  it('marks tabs paths missing from the result', () => {
    const { el, text } = render({ warnings: [{ code: 'R03_EMPTY_PAGE', message: 'm', path: 'tabs[0]' }] });
    expect(text()).toContain('tabs[0] (element nie występuje w wyniku)');
    expect(el.querySelector('button')).toBeNull();
  });

  it('shows dictionary proposals', () => {
    const { text } = render(mockReport(nadplata));
    expect(text()).toContain('rodzaj_podmiotu');
    expect(text()).toContain('Rodzaj podmiotu');
    expect(text()).toContain('Używa: tabs[0].questions[1]');
    expect(text()).toContain('2 pozycje');
  });

  it('shows processing details', () => {
    const { text } = render(mockReport(nadplata));
    expect(text()).toContain('tekst z PDF');
    expect(text()).toContain('claude-sonnet-4-5');
    expect(text()).toContain('analiza 15,8 s');
    expect(text()).toContain('25,1 s');
  });

  it('shows the rule-based draft note on fallback', () => {
    const report = { llm: { model: null, fallback: true, fallbackReason: 'timeout' } } satisfies ConversionReport;
    expect(render(report).text()).toContain('szkic regułowy (bez LLM)');
  });

  it('shows Brak for malformed fields without throwing', () => {
    const { text } = render({ warnings: 'x', stats: null });
    expect(text().match(/Brak/g)!.length).toBeGreaterThanOrEqual(3);
  });

  it('shows a message when there is no report', () => {
    expect(render(null).text()).toContain('Raport niedostępny dla tego wyniku.');
  });
});
