import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { Store, provideStore } from '@ngrx/store';
import { FileDrop } from '../../shared/ui/file-drop/file-drop';
import { ImportQueueActions as A } from '../../store/import-queue/import-queue.actions';
import {
  importQueueFeatureKey,
  importQueueReducer,
} from '../../store/import-queue/import-queue.reducer';
import { FileRegistry } from './file-registry';
import { ImportPage } from './import-page';

async function setup() {
  TestBed.configureTestingModule({
    providers: [provideRouter([]), provideStore({ [importQueueFeatureKey]: importQueueReducer })],
  });
  const fixture = TestBed.createComponent(ImportPage);
  document.body.appendChild(fixture.nativeElement);
  await fixture.whenStable();
  const el: HTMLElement = fixture.nativeElement;
  const store = TestBed.inject(Store);
  const registry = TestBed.inject(FileRegistry);
  const stable = () => fixture.whenStable();
  const addFiles = async (...files: File[]) => {
    fixture.debugElement.query(By.directive(FileDrop)).componentInstance.filesSelected.emit(files);
    await stable();
  };
  const announcement = () =>
    el.querySelector('[aria-live="polite"]')!.textContent!.replace('​', '');
  const idOf = (name: string) => [...registry['files']].find(([, f]) => f.name === name)![0];
  return { fixture, el, store, registry, stable, addFiles, announcement, idOf };
}

describe('ImportPage', () => {
  afterEach(() => (document.body.innerHTML = ''));

  it('announces added files together with validation errors', async () => {
    const { addFiles, announcement } = await setup();
    await addFiles(new File(['x'], 'a.pdf'), new File(['x'], 'b.exe'));
    expect(announcement()).toBe(
      'Dodano 2 pliki do kolejki. b.exe: błąd – Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.',
    );
  });

  it('announces finished and failed conversions', async () => {
    const { store, stable, addFiles, announcement, idOf } = await setup();
    await addFiles(new File(['x'], 'a.pdf'), new File(['x'], 'b.pdf'));
    const [a, b] = [idOf('a.pdf'), idOf('b.pdf')];
    store.dispatch(A.convertStarted({ id: a, startedAt: 1 }));
    store.dispatch(A.convertStarted({ id: b, startedAt: 1 }));
    await stable();
    store.dispatch(A.convertSucceeded({ id: a, result: {}, report: null, durationMs: 1 }));
    await stable();
    expect(announcement()).toBe('a.pdf: gotowe');
    store.dispatch(A.convertFailed({ id: b, error: 'Serwer zajęty' }));
    await stable();
    expect(announcement()).toBe('b.pdf: błąd – Serwer zajęty');
  });

  it('validates the document password before sending it', async () => {
    const { el, store, registry, stable, addFiles, idOf } = await setup();
    await addFiles(new File(['x'], 'tajny.pdf'));
    const id = idOf('tajny.pdf');
    store.dispatch(A.convertStarted({ id, startedAt: 1 }));
    store.dispatch(A.convertFailed({ id, error: 'Podaj hasło', passwordState: 'required' }));
    await stable();
    const field = () => el.querySelector<HTMLInputElement>(`[id="pw-${id}"]`)!;
    const submit = async (value: string) => {
      field().value = value;
      el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      await stable();
    };
    let describedAtFocus: string | null = null;
    field().addEventListener(
      'focus',
      () => (describedAtFocus = field().getAttribute('aria-describedby')),
    );

    await submit('');
    expect(el.querySelector(`[id="pwhint-${id}"]`)!.textContent!.trim()).toBe('Wpisz hasło.');
    expect(document.activeElement).toBe(field());
    expect(describedAtFocus).toContain(`pwhint-${id}`);

    await submit('ą'.repeat(513)); // 1026 UTF-8 bytes
    expect(el.querySelector(`[id="pwhint-${id}"]`)!.textContent!.trim()).toBe(
      'Hasło jest za długie (najwyżej 1024 bajty).',
    );
    expect(registry.password(id)).toBeUndefined();

    await submit('ą'.repeat(512)); // exactly 1024 bytes
    expect(registry.password(id)).toBe('ą'.repeat(512));
    expect(el.querySelector(`[id="pwhint-${id}"]`)).toBeNull();
    expect(el.querySelector('form')).toBeNull(); // back to pending
  });

  it('warns before unload only while files are pending or processing', async () => {
    const { fixture, addFiles } = await setup();
    const unload = () => {
      const event = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    };
    expect(unload()).toBe(false);
    await addFiles(new File(['x'], 'a.pdf'));
    expect(unload()).toBe(true);
    fixture.destroy();
  });

  it('explains the ZIP button while nothing is done and ignores clicks', async () => {
    const { el } = await setup();
    const zip = [...el.querySelectorAll('button')].find((b) => b.textContent!.includes('ZIP'))!;
    expect(zip.getAttribute('aria-disabled')).toBe('true');
    expect(el.querySelector(`#${zip.getAttribute('aria-describedby')}`)!.textContent).toContain(
      'przetworzony',
    );
    const importSpy = vi.spyOn(URL, 'createObjectURL');
    zip.click();
    expect(importSpy).not.toHaveBeenCalled();
  });
});
