import { findDictionary, DictionaryNode } from './sample-dictionaries';
import { FormField } from './form-definition';
import { isEmptyAnswer, validateField } from './validators';

const f = (type: string, validation: string[], extra: Partial<FormField> = {}): FormField => ({
  id: 'x',
  techName: 't',
  title: 'T',
  type,
  validation,
  ...extra,
});

const MSG = {
  PESEL: 'PESEL ma 11 cyfr',
  NIP: 'NIP ma 10 cyfr',
  REGON: 'REGON ma 9 lub 14 cyfr',
  ZIP_CODE: 'Wpisz kod w formacie 00-000',
  EMAIL: 'Wpisz adres e-mail, np. jan@domena.pl',
  EPUAP: 'Wpisz adres skrytki ePUAP, np. /urzad/SkrytkaESP',
  ADE: 'Wpisz adres do e-Doręczeń, np. AE:PL-12345-67890-ABCDE-12',
  SERIAL_NUMBER_ID_CARD: 'Wpisz serię i numer dowodu: 3 litery i 6 cyfr',
} as const;

const valid: [keyof typeof MSG, string][] = [
  ['PESEL', '44051401458'],
  ['PESEL', '440 514 014 58'],
  ['NIP', '1234563218'],
  ['NIP', '123-456-32-18'],
  ['REGON', '123456785'],
  ['REGON', '12345678901235'],
  ['ZIP_CODE', '00-001'],
  ['EMAIL', 'jan@domena.pl'],
  ['EPUAP', '/urzad/SkrytkaESP'],
  ['ADE', 'AE:PL-12345-67890-ABCDE-12'],
  ['ADE', 'ae:pl-12345-67890-abcde-12'],
  ['SERIAL_NUMBER_ID_CARD', 'ABA300000'],
  ['SERIAL_NUMBER_ID_CARD', 'aba300000'],
];
const invalid: [keyof typeof MSG, string][] = [
  ['PESEL', '4405140145'],
  ['NIP', '123456321'],
  ['NIP', '12345632181'],
  ['REGON', '1234567890'],
  ['ZIP_CODE', '00001'],
  ['EMAIL', 'jan@domena'],
  ['EPUAP', 'urzad/Skrytka'],
  ['ADE', 'AE:PL-1234-67890-ABCDE-12'],
  ['SERIAL_NUMBER_ID_CARD', 'ABA300001'],
  ['SERIAL_NUMBER_ID_CARD', 'AB1300000'],
];

describe('validateField', () => {
  it.each(valid)('%s accepts %s', (code, value) => {
    expect(validateField(f('TEXT_FIELD', [code]), value)).toBeNull();
  });

  it.each(invalid)('%s rejects %s', (code, value) => {
    expect(validateField(f('TEXT_FIELD', [code]), value)).toBe(MSG[code]);
  });

  // Right length, wrong check digit: the message must not claim the length is wrong.
  it.each([
    ['PESEL', '44051401459'],
    ['NIP', '1234563219'],
    ['NIP', '123-456-32-19'],
    ['REGON', '123456784'],
    ['REGON', '12345678901234'],
  ])('%s with a wrong check digit %s says so', (code, value) => {
    expect(validateField(f('TEXT_FIELD', [code]), value)).toBe(
      `Nieprawidłowy ${code} - sprawdź, czy cyfry są wpisane poprawnie`,
    );
  });

  it('NUMBER accepts only numbers, with comma or dot and spaces', () => {
    for (const ok of ['1250', '1 250,50', '-3.5'])
      expect(validateField(f('NUMBER', []), ok)).toBeNull();
    for (const bad of ['abc', '12 zł', '1,2,3'])
      expect(validateField(f('NUMBER', []), bad)).toBe('Wpisz liczbę, np. 1250,50');
  });

  it('tolerates a non-array validation from imported JSON', () => {
    const field = f('TEXT_FIELD', {} as unknown as string[]);
    expect(validateField(field, '')).toBeNull();
  });

  it('skips format checks on empty optional values, but REQUIRED wins', () => {
    expect(validateField(f('TEXT_FIELD', ['PESEL']), '')).toBeNull();
    expect(validateField(f('TEXT_FIELD', ['REQUIRED', 'PESEL']), '')).toBe('Uzupełnij to pole');
  });

  it('REQUIRED depends on the field type', () => {
    const req = (type: string, answer: unknown) => validateField(f(type, ['REQUIRED']), answer);
    expect(req('TEXT_FIELD', '  ')).toBe('Uzupełnij to pole');
    expect(req('NUMBER', '0')).toBeNull();
    expect(req('SELECT', '')).toBe('Wybierz jedną z opcji');
    expect(req('RADIO', '')).toBe('Wybierz jedną z opcji');
    expect(req('CHECKBOX', [])).toBe('Zaznacz to pole');
    expect(req('FILE_UPLOADER', [])).toBe('Dodaj plik');
    expect(req('DATEPICKER', '')).toBe('Uzupełnij to pole');
  });

  it('CONSENT_SECTION with required: true needs every consent, even without REQUIRED', () => {
    const consents = [{ description: 'a' }, { description: 'b' }];
    const field = f('CONSENT_SECTION', [], { consentSectionConfig: { consents, required: true } });
    expect(validateField(field, [false, true])).toBe('Zaznacz wymaganą zgodę');
    expect(validateField(field, [true, false])).toBe('Zaznacz wymaganą zgodę');
    expect(validateField(field, [true, true])).toBeNull();
    const optional = f('CONSENT_SECTION', [], {
      consentSectionConfig: { consents, required: false },
    });
    expect(validateField(optional, [false, false])).toBeNull();
  });

  it('cascade is empty until the path reaches a leaf', () => {
    const field = f('SELECT', ['REQUIRED'], { dictionaryName: 'TERYT_4G_DOWODOWY' });
    expect(validateField(field, [])).toBe('Wybierz jedną z opcji');
    expect(validateField(field, ['mazowieckie'])).toBe('Wybierz jedną z opcji');
    const path: string[] = [];
    let level: DictionaryNode[] | undefined = findDictionary('TERYT_4G_DOWODOWY')!.items;
    while (level?.length) {
      path.push(level[0].name);
      level = level[0].children;
    }
    expect(path.length).toBe(4);
    expect(validateField(field, path)).toBeNull();
    expect(isEmptyAnswer(field, path)).toBe(false);
  });

  it('ignores an unknown code with one warning per code', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const field = f('TEXT_FIELD', ['FOO']);
    expect(validateField(field, 'a')).toBeNull();
    expect(validateField(field, 'b')).toBeNull();
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });
});
