import { DictionaryNode, findDictionary } from './sample-dictionaries';
import { FormField } from './form-definition';
import { isCascade } from './select-options';

const REQUIRED_MESSAGES: Record<string, string> = {
  SELECT: 'Wybierz jedną z opcji',
  RADIO: 'Wybierz jedną z opcji',
  CHECKBOX: 'Zaznacz to pole',
  CONSENT_SECTION: 'Zaznacz wymaganą zgodę',
  FILE_UPLOADER: 'Dodaj plik',
};

const sum = (digits: string, weights: number[]) =>
  weights.reduce((acc, w, i) => acc + w * Number(digits[i]), 0);

const regon = (v: string) => {
  const weights =
    v.length === 9 ? [8, 9, 2, 3, 4, 5, 6, 7] : [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8];
  return (sum(v, weights) % 11) % 10 === Number(v[v.length - 1]);
};

const idCard = (v: string) => {
  const weights = [7, 3, 1, 9, 7, 3, 1, 7, 3];
  return weights.reduce((acc, w, i) => acc + w * parseInt(v[i], 36), 0) % 10 === 0;
};

interface FormatRule {
  message: string;
  /** Strip spaces and dashes before checking. */
  digitsOnly?: boolean;
  test: (value: string) => boolean;
  /** Runs once the format passes: a wrong check digit gets its own message, not "11 digits". */
  checksum?: { message: string; test: (value: string) => boolean };
}

const FORMAT_RULES: Record<string, FormatRule> = {
  PESEL: {
    message: 'PESEL ma 11 cyfr',
    digitsOnly: true,
    test: (v) => /^\d{11}$/.test(v),
    checksum: {
      message: 'Nieprawidłowy PESEL - sprawdź, czy cyfry są wpisane poprawnie',
      test: (v) => (10 - (sum(v, [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]) % 10)) % 10 === Number(v[10]),
    },
  },
  NIP: {
    message: 'NIP ma 10 cyfr',
    digitsOnly: true,
    test: (v) => /^\d{10}$/.test(v),
    checksum: {
      message: 'Nieprawidłowy NIP - sprawdź, czy cyfry są wpisane poprawnie',
      test: (v) => sum(v, [6, 5, 7, 2, 3, 4, 5, 6, 7]) % 11 === Number(v[9]),
    },
  },
  REGON: {
    message: 'REGON ma 9 lub 14 cyfr',
    digitsOnly: true,
    test: (v) => /^(\d{9}|\d{14})$/.test(v),
    checksum: {
      message: 'Nieprawidłowy REGON - sprawdź, czy cyfry są wpisane poprawnie',
      test: regon,
    },
  },
  ZIP_CODE: { message: 'Wpisz kod w formacie 00-000', test: (v) => /^\d{2}-\d{3}$/.test(v) },
  EMAIL: {
    message: 'Wpisz adres e-mail, np. jan@domena.pl',
    test: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
  },
  EPUAP: {
    message: 'Wpisz adres skrytki ePUAP, np. /urzad/SkrytkaESP',
    test: (v) => /^\/[^/\s]+\/[^/\s]+$/.test(v),
  },
  ADE: {
    message: 'Wpisz adres do e-Doręczeń, np. AE:PL-12345-67890-ABCDE-12',
    test: (v) => /^AE:PL-\d{5}-\d{5}-[A-Z]{5}-\d{2}$/i.test(v),
  },
  SERIAL_NUMBER_ID_CARD: {
    message: 'Wpisz serię i numer dowodu: 3 litery i 6 cyfr',
    test: (v) => /^[A-Z]{3}\d{6}$/i.test(v) && idCard(v),
  },
};

const warned = new Set<string>();

/** The cascade is complete once the path ends at a node without children. */
function cascadeComplete(field: FormField, path: unknown): boolean {
  if (!Array.isArray(path) || !path.length) return false;
  let level: DictionaryNode[] | undefined = findDictionary(field.dictionaryName)?.items;
  let node: DictionaryNode | undefined;
  for (const name of path) {
    node = level?.find((n) => n.name === name);
    if (!node) return false;
    level = node.children;
  }
  return !node?.children?.length;
}

export function isEmptyAnswer(field: FormField, answer: unknown): boolean {
  if (field.type === 'CONSENT_SECTION') {
    const consents = field.consentSectionConfig?.consents ?? [];
    const given = Array.isArray(answer) ? answer : [];
    const required = field.consentSectionConfig?.required === true;
    return required && consents.some((_, i) => !given[i]);
  }
  if (field.type === 'SELECT' && isCascade(field)) return !cascadeComplete(field, answer);
  if (Array.isArray(answer)) return answer.length === 0;
  return typeof answer !== 'string' || answer.trim() === '';
}

/** First error message, or null. REQUIRED runs first, then format codes in order; unknown codes are ignored. */
export function validateField(field: FormField, answer: unknown): string | null {
  // Imported JSON is untrusted: anything but an array means no codes.
  const codes = Array.isArray(field.validation) ? field.validation : [];
  const empty = isEmptyAnswer(field, answer);
  // A consent section is always checked: its required flags live in the config, not in `validation`.
  if (empty && (codes.includes('REQUIRED') || field.type === 'CONSENT_SECTION')) {
    return REQUIRED_MESSAGES[field.type] ?? 'Uzupełnij to pole';
  }
  if (empty || typeof answer !== 'string') return null;
  // NUMBER carries no format code (only REQUIRED is allowed): the type itself is the rule.
  if (field.type === 'NUMBER' && !/^-?\d+(?:[.,]\d+)?$/.test(answer.replace(/\s/g, ''))) {
    return 'Wpisz liczbę, np. 1250,50';
  }
  for (const code of codes) {
    if (code === 'REQUIRED') continue;
    const rule = FORMAT_RULES[code];
    if (!rule) {
      if (!warned.has(code)) {
        warned.add(code);
        console.warn(`Unknown validator code: ${code}`);
      }
      continue;
    }
    const value = answer.trim();
    const checked = rule.digitsOnly ? value.replace(/[\s-]/g, '') : value;
    if (!rule.test(checked)) return rule.message;
    if (rule.checksum && !rule.checksum.test(checked)) return rule.checksum.message;
  }
  return null;
}
