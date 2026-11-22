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

  it('emits the key of an accepted warning, hides it and lets the user restore it', () => {
    const { fixture, el } = render(mockReport(nadplata));
    const keys: string[] = [];
    let restored = 0;
    fixture.componentInstance.acceptWarning.subscribe((k) => keys.push(k));
    fixture.componentInstance.restoreWarnings.subscribe(() => restored++);
    const btn = el.querySelector<HTMLButtonElement>('button[aria-label="Zaakceptuj ostrzeżenie: W07_CHOICE_OPTIONS"]')!;
    btn.click();
    expect(keys).toHaveLength(1);
    expect(keys[0]).toContain('W07_CHOICE_OPTIONS');
    expect(el.querySelector('button[aria-label^="Zaakceptuj ostrzeżenie: W07"]')).not.toBeNull();
    expect(el.querySelectorAll('button[aria-label^="Zaakceptuj ostrzeżenie"]')).toHaveLength(3);
    expect(el.querySelector('button[aria-label^="Zaakceptuj"][aria-label*="fix"]')).toBeNull();

    fixture.componentRef.setInput('accepted', keys);
    fixture.detectChanges();
    expect(el.querySelector('button[aria-label="Zaakceptuj ostrzeżenie: W07_CHOICE_OPTIONS"]')).toBeNull();
    expect(el.querySelector('h2')!.textContent!.trim()).toBe('Ostrzeżenia (2)');
    expect(el.textContent).toContain('Zaakceptowane i ukryte: 1');
    [...el.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent!.trim() === 'Przywróć')!.click();
    expect(restored).toBe(1);
  });

  it('emits the path from the show-in-JSON button of a linkable issue', () => {
    const { fixture, el } = render(mockReport(nadplata));
    const paths: string[] = [];
    fixture.componentInstance.showInJson.subscribe((p) => paths.push(p));
    const btn = el.querySelector<HTMLButtonElement>('button[aria-label="Pokaż w JSON: R12_DUPLICATE_TECH_NAME"]')!;
    expect(btn.textContent!.trim()).toBe('Pokaż w JSON');
    btn.click();
    expect(paths).toEqual(['tabs[1].questions[0].field.repeatingSectionGrid[1]']);
  });

  it('puts the accept button right under the warning, with no jump-to buttons on warnings', () => {
    const { el } = render(mockReport(nadplata));
    const warning = el.querySelector('section')!;
    expect(warning.querySelector('button[aria-label^="Pokaż w JSON"]')).toBeNull();
    expect(warning.querySelector('button[aria-label^="Pokaż w edycji"]')).toBeNull();
    const row = warning.querySelector('li')!;
    const message = row.querySelector('div > div')!;
    const accept = row.querySelector('button[aria-label^="Zaakceptuj"]')!;
    expect(message.nextElementSibling).toBe(accept);
  });

  it('shows warnings as message only, without code or draft path', () => {
    const { el, text } = render(mockReport(nadplata));
    expect(text()).not.toContain('W03_UNPLACED_FIELD');
    expect(text()).not.toContain('miejsce w szkicu');
    expect(el.querySelector('button[aria-label="Pokaż w JSON: W03_UNPLACED_FIELD"]')).toBeNull();
  });

  it('does not show paths missing from the result, nor a JSON button for them', () => {
    const { el, text } = render({ warnings: [{ code: 'R03_EMPTY_PAGE', message: 'm', path: 'tabs[0]' }] });
    expect(text()).not.toContain('element nie występuje');
    expect(el.querySelector('button[aria-label^="Pokaż w JSON"]')).toBeNull();
  });

  it('emits the editor id from the show-in-editor button of a warning', () => {
    const path = 'tabs[1].questions[0].field.repeatingSectionGrid[1]';
    const fixture = TestBed.createComponent(ReportView);
    fixture.componentRef.setInput('report', asReport({ fixes: [{ code: 'W1', message: 'm', path }] }));
    fixture.componentRef.setInput('ranges', ranges);
    fixture.componentRef.setInput('paths', new Map([['pole', path]]));
    fixture.componentRef.setInput('editIds', new Map([['pole', 'row-7']]));
    fixture.detectChanges();
    const ids: string[] = [];
    fixture.componentInstance.showInEditor.subscribe((id) => ids.push(id));
    fixture.nativeElement.querySelector('button[aria-label="Pokaż w edycji: W1"]').click();
    expect(ids).toEqual(['row-7']);
  });

  it('shows dictionary proposals', () => {
    const { text } = render(mockReport(nadplata));
    expect(text()).toContain('rodzaj_podmiotu');
    expect(text()).toContain('Rodzaj podmiotu');
    expect(text()).toContain('Używa: wybierz_jako_kto_wnioskujesz');
    expect(text()).toContain('2 pozycje');
    expect(text()).toContain('Lista rodzajów podmiotów składających wniosek.');
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

  it('tolerates malformed entries and values', () => {
    const { el, text } = render({
      warnings: [null, 'x', { code: 1, message: {}, path: 5 }, { code: 'W1', message: 'ok', path: 'tabs[0]' }],
      fixes: [null],
      dictionaryProposals: [null, { name: 'd', items: 'x', usedBy: 'y' }],
      stats: { tabs: {}, fields: NaN, sections: 2 },
      timings: { analyzeMs: 'x', buildMs: 1000 },
      durationMs: {},
    });
    expect(el.querySelectorAll('h2')[0].textContent).toContain('(2)');
    expect(text()).toContain('Sekcje2');
    expect(text()).not.toMatch(/object|NaN/);
    expect(text()).toContain('budowa 1,0 s');
    expect(text()).not.toContain('analiza');
    expect(text()).toContain('0 pozycji');
  });

  it('shows Brak in Przetwarzanie when there is nothing to show', () => {
    const { el } = render({ timings: { x: 'a' } });
    const section = [...el.querySelectorAll('section')].find((s) => s.querySelector('h2')!.textContent === 'Przetwarzanie')!;
    expect(section.textContent).toContain('Brak');
    expect(section.querySelector('dd')).toBeNull();
  });

  it('shows a message when there is no report', () => {
    expect(render(null).text()).toContain('Raport niedostępny dla tego wyniku.');
  });
});
