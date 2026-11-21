import { InjectionToken } from '@angular/core';
import { Observable } from 'rxjs';

export const BATCH_CONCURRENCY = 2;

// NOTE: FormsService.convertApiV1FormsConvertPost now declares the multipart body ({file, password?}); a real provider
// can call it instead of the mock (see provideMockConvertFile in app.config.ts).
export type ConvertFileFn = (file: File) => Observable<unknown>;

export const CONVERT_FILE = new InjectionToken<ConvertFileFn>('CONVERT_FILE');
