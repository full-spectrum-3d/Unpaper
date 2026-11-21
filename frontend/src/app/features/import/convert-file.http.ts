import { Provider, inject } from '@angular/core';
import { FormsService } from '../../shared/api/services/forms.service';
import { CONVERT_FILE, ConvertFileFn } from './convert-file';

// POST /api/v1/forms/convert (multipart fields `file` and optional `password`); authInterceptor adds the bearer token.
export const provideHttpConvertFile = (): Provider => ({
  provide: CONVERT_FILE,
  useFactory: (): ConvertFileFn => {
    const forms = inject(FormsService);
    return (file, password) =>
      forms.convertApiV1FormsConvertPost({ body: password ? { file, password } : { file } });
  },
});
