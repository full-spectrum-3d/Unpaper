import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { FormDefinition } from './form-definition';
import { FormRenderer } from './form-renderer';

describe('FormRenderer visibility', () => {
  let fixture: ComponentFixture<FormRenderer>;
  const el = () => fixture.nativeElement as HTMLElement;
  const radio = (name: string) =>
    [...el().querySelectorAll<HTMLInputElement>('input[type=radio]')].find(
      (r) => r.value === name,
    )!;
  const hasHeading = (name: string) =>
    [...el().querySelectorAll('h4')].some((h) => h.textContent?.trim() === name);

  beforeEach(async () => {
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(FormRenderer);
    fixture.componentRef.setInput('definition', nadplata as unknown as FormDefinition);
    await fixture.whenStable();
  });

  it('shows a conditional section once its answer is given', async () => {
    expect(hasHeading('Dane innej osoby')).toBe(false);
    radio('Innej osoby').click();
    await fixture.whenStable();
    expect(hasHeading('Dane innej osoby')).toBe(true);
  });

  it('latest answers win', async () => {
    radio('Innej osoby').click();
    radio('Swoim').click();
    await fixture.whenStable();
    expect(hasHeading('Dane innej osoby')).toBe(false);
  });
});
