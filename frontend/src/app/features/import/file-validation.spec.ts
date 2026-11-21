import { validateFile } from './file-validation';

const MB = 1024 * 1024;
const file = (name: string, size = 100) => ({ name, size });

const TOO_LONG = 'Nazwa pliku jest za długa (maks. 250 znaków).';
const BAD_CHARS = "Nazwa pliku zawiera niedozwolone znaki: ; : > < / \\ | ' * % $";
const TOO_BIG = 'Plik jest za duży (maks. 20 MB).';
const BAD_EXT = 'Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.';

describe('validateFile', () => {
  it('accepts valid pdf', () => {
    expect(validateFile(file('raport.pdf'))).toBeNull();
  });

  it('accepts uppercase extension', () => {
    expect(validateFile(file('A.PDF'))).toBeNull();
  });

  it('rejects name over 250', () => {
    expect(validateFile(file('a'.repeat(246) + '.pdf'))).toBeNull();
    expect(validateFile(file('a'.repeat(247) + '.pdf'))).toBe(TOO_LONG);
  });

  it.each([';', ':', '>', '<', '/', '\\', '|', "'", '*', '%', '$'])('rejects forbidden character %s', (ch) => {
    expect(validateFile(file(`a${ch}b.pdf`))).toBe(BAD_CHARS);
  });

  it('rejects over 20 MB', () => {
    expect(validateFile(file('a.pdf', 20 * MB))).toBeNull();
    expect(validateFile(file('a.pdf', 20 * MB + 1))).toBe(TOO_BIG);
  });

  it('rejects unsupported extension', () => {
    expect(validateFile(file('a.jpe'))).toBe(BAD_EXT);
  });

  it.each(['raport', 'raport.'])('rejects missing extension %s', (name) => {
    expect(validateFile(file(name))).toBe(BAD_EXT);
  });

  it('accepts empty file', () => {
    expect(validateFile(file('a.pdf', 0))).toBeNull();
  });

  it('applies rules in order', () => {
    expect(validateFile(file('a'.repeat(251) + ';', 21 * MB))).toBe(TOO_LONG);
    expect(validateFile(file('a;b.xyz', 21 * MB))).toBe(BAD_CHARS);
    expect(validateFile(file('a.xyz', 21 * MB))).toBe(TOO_BIG);
  });
});
