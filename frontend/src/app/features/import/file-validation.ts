export const MAX_FILE_SIZE_MB = 20;
export const ACCEPTED_EXTENSIONS: readonly string[] = ['pdf', 'doc', 'docx', 'ods', 'xlsx', 'jpg', 'jpeg', 'png'];

const MAX_NAME_LENGTH = 250;
// Mirrors backend upload_validation/filename.py: listed characters plus control characters (Cc).
const FORBIDDEN_CHARS = /[;:><\/\\|'*%$\p{Cc}]/u;

function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot === -1 || dot === name.length - 1 ? '' : name.slice(dot + 1).toLowerCase();
}

export function validateFile(file: Pick<File, 'name' | 'size'>): string | null {
  // NFC like the backend: "ą" as two code points counts as one character.
  const name = file.name.normalize('NFC');
  // Code points, as Python's len() counts them (not UTF-16 units).
  if ([...name].length > MAX_NAME_LENGTH) return `Nazwa pliku jest za długa (maks. ${MAX_NAME_LENGTH} znaków).`;
  if (FORBIDDEN_CHARS.test(name)) return "Nazwa pliku zawiera niedozwolone znaki: ; : > < / \\ | ' * % $";
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) return `Plik jest za duży (maks. ${MAX_FILE_SIZE_MB} MB).`;
  if (!ACCEPTED_EXTENSIONS.includes(extensionOf(name))) {
    return 'Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.';
  }
  if (!name.slice(0, name.lastIndexOf('.')).trim()) return 'Nazwa pliku nie może składać się z samego rozszerzenia.';
  return null;
}
