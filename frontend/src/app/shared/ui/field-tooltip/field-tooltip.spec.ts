import { Component, provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FieldTooltip } from './field-tooltip';

@Component({
  imports: [FieldTooltip],
  template: `<app-field-tooltip label="Numer PESEL" text="Jedenaście <b>cyfr</b>" />`,
})
class Host {}

describe('FieldTooltip', () => {
  let fixture: ComponentFixture<Host>;
  let button: HTMLButtonElement;
  const panel = () =>
    fixture.nativeElement.querySelector(`#${button.getAttribute('aria-controls')}`);
  const render = async () => {
    fixture.detectChanges();
    await fixture.whenStable();
  };

  beforeEach(async () => {
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(Host);
    await render();
    button = fixture.nativeElement.querySelector('button');
  });

  it('is collapsed with an accessible name', () => {
    expect(button.getAttribute('aria-label')).toBe('Więcej informacji: Numer PESEL');
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(panel().textContent.trim()).toBe('');
    expect(panel().getAttribute('aria-live')).toBe('polite');
  });

  it('toggles on click and renders HTML text', async () => {
    button.click();
    await render();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(panel().textContent.trim()).toBe('Jedenaście cyfr');
    expect(panel().querySelector('b')).not.toBeNull();
    button.click();
    await render();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(panel().textContent.trim()).toBe('');
  });

  it('collapses on Escape', async () => {
    button.click();
    await render();
    button.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await render();
    expect(button.getAttribute('aria-expanded')).toBe('false');
  });
});
