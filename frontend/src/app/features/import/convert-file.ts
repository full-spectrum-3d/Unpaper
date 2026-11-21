import { InjectionToken } from '@angular/core';
import { Observable } from 'rxjs';

export const BATCH_CONCURRENCY = 2;

// NOTE: the generated FormsService.convertApiV1FormsConvertPost has no request body yet, so a real provider needs the
// backend OpenAPI to declare a multipart file upload (then regenerate) or a hand-written HttpClient.post with FormData.
export type ConvertFileFn = (file: File) => Observable<unknown>;

export const CONVERT_FILE = new InjectionToken<ConvertFileFn>('CONVERT_FILE');
