import { InjectionToken } from '@angular/core';
import { Observable } from 'rxjs';

export const BATCH_CONCURRENCY = 2;

// App: provideHttpConvertFile (convert-file.http.ts). Offline demo without the API: provideMockConvertFile.
/** `password` unlocks a protected document (after DOCUMENT_PASSWORD_REQUIRED/INVALID). */
export type ConvertFileFn = (file: File, password?: string) => Observable<unknown>;

export const CONVERT_FILE = new InjectionToken<ConvertFileFn>('CONVERT_FILE');
