import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AnswersStore } from '../answers-store';
import { FormField } from '../form-definition';
import { FormState } from '../form-state';
import { FileUploaderField, fileProblem } from './file-uploader';

describe('fileProblem', () => {
  it('accepts listed formats up to 10 MB', () => {
    expect(fileProblem({ name: 'skan.PDF', size: 10 * 1024 * 1024 })).toBeNull();
  });

  it('rejects other formats and larger files', () => {
    expect(fileProblem({ name: 'wirus.exe', size: 1 })).toContain('niedozwolony format');
    expect(fileProblem({ name: 'bez-rozszerzenia', size: 1 })).toContain('niedozwolony format');
    expect(fileProblem({ name: 'duzy.jpg', size: 10 * 1024 * 1024 + 1 })).toContain('10 MB');
  });
});

describe('FileUploaderField', () => {
  let fixture: ComponentFixture<FileUploaderField>;
  let store: AnswersStore;
  const field = {
    id: 'plik',
    type: 'FILE_UPLOADER',
    techName: 'plik',
    title: 'Załącznik',
  } as FormField;
  const el = () => fixture.nativeElement as HTMLElement;
  const status = () => el().querySelector('[role=status]')!.textContent!.trim();
  const choose = async (...files: File[]) => {
    const input = el().querySelector<HTMLInputElement>('input[type=file]')!;
    Object.defineProperty(input, 'files', { value: files, configurable: true });
    input.dispatchEvent(new Event('change'));
    await fixture.whenStable();
  };

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), AnswersStore, FormState],
    });
    store = TestBed.inject(AnswersStore);
    fixture = TestBed.createComponent(FileUploaderField);
    fixture.componentRef.setInput('field', field);
    await fixture.whenStable();
  });

  it('keeps only the first file and announces it', async () => {
    await choose(new File(['a'], 'a.pdf'), new File(['b'], 'b.pdf'));
    expect(store.answer(field)()).toEqual(['a.pdf']);
    expect(status()).toBe('Dodano plik a.pdf');
  });

  it('rejects a file of a wrong type with a linked error', async () => {
    await choose(new File(['x'], 'x.exe'));
    expect(store.answer(field)()).toEqual([]);
    const error = el().querySelector('small.text-danger')!;
    expect(error.textContent).toContain('niedozwolony format');
    const button = el().querySelector('button')!;
    expect(button.getAttribute('aria-describedby')?.split(' ')).toContain(error.id);
    expect(button.getAttribute('aria-invalid')).toBe('true');
  });

  it('removes the file with a named button', async () => {
    await choose(new File(['a'], 'a.pdf'));
    el().querySelector<HTMLButtonElement>('button[aria-label="Usuń plik a.pdf"]')!.click();
    await fixture.whenStable();
    expect(store.answer(field)()).toEqual([]);
    expect(status()).toBe('Usunięto plik a.pdf');
  });

  it('renders the description after the label', () => {
    fixture.componentRef.setInput('field', { ...field, description: 'Opis' });
    fixture.detectChanges();
    const label = el().querySelector('#fld-plik-label')!;
    const desc = el().querySelector('#fld-plik-desc')!;
    expect(label.compareDocumentPosition(desc) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
