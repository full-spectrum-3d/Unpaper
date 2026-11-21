import { InjectionToken } from '@angular/core';
import { Observable } from 'rxjs';

export const BATCH_CONCURRENCY = 2;

// App: provideHttpConvertFile (convert-file.http.ts). Offline demo without the API: provideMockConvertFile.
export type ConvertFileFn = (file: File) => Observable<unknown>;

export const CONVERT_FILE = new InjectionToken<ConvertFileFn>('CONVERT_FILE');
