import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideApiConfiguration } from '../../shared/api/api-configuration';
import { CONVERT_FILE } from './convert-file';
import { provideHttpConvertFile } from './convert-file.http';

describe('provideHttpConvertFile', () => {
  it('posts the file as multipart to /api/v1/forms/convert', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration(''),
        provideHttpConvertFile(),
      ],
    });
    const convert = TestBed.inject(CONVERT_FILE);
    const ctrl = TestBed.inject(HttpTestingController);
    let result: unknown;
    convert(new File(['x'], 'wniosek.pdf')).subscribe((r) => (result = r));

    const req = ctrl.expectOne((r) => r.url === '/api/v1/forms/convert');
    expect(req.request.method).toBe('POST');
    const body = req.request.body as FormData;
    expect((body.get('file') as File).name).toBe('wniosek.pdf');
    req.flush({ title: 'Wniosek' });
    expect(result).toEqual({ title: 'Wniosek' });
    ctrl.verify();
  });
});
