import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Progress } from './progress';

@Component({
  imports: [Progress],
  template: `<app-progress label="Postęp" [value]="value()" [valueText]="text()" />`,
})
class Host {
  readonly value = signal<number | undefined>(undefined);
  readonly text = signal<string | undefined>(undefined);
}

describe('Progress', () => {
  const setup = () => {
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const bar = () => fixture.nativeElement.querySelector('[role=progressbar]') as HTMLElement;
    return { fixture, bar };
  };

  it('is indeterminate without a value', () => {
    const { bar } = setup();
    expect(bar().hasAttribute('aria-valuenow')).toBe(false);
    expect(bar().querySelector('.bar')).not.toBeNull();
  });

  it('exposes a clamped, rounded value and its text', () => {
    const { fixture, bar } = setup();
    fixture.componentInstance.value.set(66.6);
    fixture.componentInstance.text.set('Krok 2 z 3');
    fixture.detectChanges();
    expect(bar().getAttribute('aria-valuenow')).toBe('67');
    expect(bar().getAttribute('aria-valuemin')).toBe('0');
    expect(bar().getAttribute('aria-valuemax')).toBe('100');
    expect(bar().getAttribute('aria-valuetext')).toBe('Krok 2 z 3');
    expect((bar().firstElementChild as HTMLElement).style.width).toBe('67%');
    fixture.componentInstance.value.set(140);
    fixture.detectChanges();
    expect(bar().getAttribute('aria-valuenow')).toBe('100');
  });
});
