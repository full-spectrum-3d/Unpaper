import {
  extractPosition,
  MAX_JSON_FILE_BYTES,
  parseJsonInput,
  positionToLineColumn,
  readJsonFile,
} from './json-input';

const NOT_OBJECT = 'JSON musi być obiektem formularza (zaczynać się od {).';
const BAD_FILE = 'Wgraj plik .json do 5 MB.';
const BROKEN = '{\n  "a": 1,\n  "b": \n}';

describe('parseJsonInput', () => {
  it('parses an object', () => {
    expect(parseJsonInput('{"a":1}')).toEqual({ ok: true, value: { a: 1 } });
  });

  it('tolerates BOM and surrounding whitespace', () => {
    expect(parseJsonInput('﻿  {"a":1}\n')).toEqual({ ok: true, value: { a: 1 } });
  });

  it.each(['[1]', '"x"', 'null', '5'])('rejects non-object %s', (text) => {
    expect(parseJsonInput(text)).toEqual({ ok: false, message: NOT_OBJECT });
  });

  it('reports line and column of a syntax error', () => {
    expect(parseJsonInput(BROKEN)).toEqual({
      ok: false,
      message: 'Niepoprawny JSON: linia 4, kolumna 1.',
    });
  });

  it('counts CRLF as one line break', () => {
    expect(parseJsonInput(BROKEN.replace(/\n/g, '\r\n'))).toEqual({
      ok: false,
      message: 'Niepoprawny JSON: linia 4, kolumna 1.',
    });
  });

  it('keeps leading blank lines in the line count', () => {
    expect(parseJsonInput('\n\n{"a":}')).toEqual({
      ok: false,
      message: 'Niepoprawny JSON: linia 3, kolumna 6.',
    });
  });

  it('falls back to a plain message without position', () => {
    expect(parseJsonInput('{"a":')).toEqual({ ok: false, message: 'Niepoprawny JSON.' });
  });
});

describe('positionToLineColumn', () => {
  it('is 1-based', () => {
    expect(positionToLineColumn('ab\ncd', 4)).toEqual({ line: 2, column: 2 });
    expect(positionToLineColumn('x', 0)).toEqual({ line: 1, column: 1 });
  });
});

describe('extractPosition', () => {
  it('reads "at position N"', () => {
    expect(extractPosition('Unexpected token } in JSON at position 17', 'x'.repeat(30))).toBe(17);
  });

  it('converts "line L column K"', () => {
    expect(extractPosition('Bad JSON (line 3 column 8)', 'ab\ncd\nefghijkl')).toBe(3 + 3 + 7);
  });

  it('locates the token from the snippet of a message without position', () => {
    const message = 'Unexpected token \'}\', ...",\n  "b": \n}" is not valid JSON';
    expect(extractPosition(message, BROKEN)).toBe(BROKEN.length - 1);
  });

  it('clamps a Firefox column to the line length', () => {
    expect(extractPosition('(line 1 column 99)', 'ab\ncd')).toBe(2);
  });

  it('snippet with leading ellipsis: unique snippet only', () => {
    const text = '{"a":1,"b":2,"c":,"d":4,"e":5}';
    const snippet = text.slice(7, 27);
    const msg = `Unexpected token ',', ..."${snippet}"... is not valid JSON`;
    expect(extractPosition(msg, text)).toBe(17);
    expect(extractPosition(msg, text + snippet)).toBeNull();
  });

  it('snippet with trailing ellipsis only: position is length - 10', () => {
    const text = '{"a":,"b":2,"c":3,"d":4,"e":5}';
    const msg = `Unexpected token ',', "${text.slice(0, 15)}"... is not valid JSON`;
    expect(extractPosition(msg, text)).toBe(5);
    expect(extractPosition(msg, 'x' + text)).toBeNull();
  });

  it('whole text shown: ambiguous token gives null', () => {
    const text = '{"a":1,"b":,"c":2}';
    const msg = `Unexpected token ',', "${text}" is not valid JSON`;
    expect(extractPosition(msg, text)).toBeNull();
    expect(
      extractPosition(
        `Unexpected token '}', "{\"a\":}" is not valid JSON`.replace(/\\/g, ''),
        '{"a":}',
      ),
    ).toBe(5);
  });

  it('never reports a wrong location for real engine errors', () => {
    for (const [text, column] of [
      ['{"a":1,"b":,"c":2}', 12],
      ['{"t":"}","x":}', 14],
    ] as const) {
      const r = parseJsonInput(text);
      expect(r.ok).toBe(false);
      if (!r.ok)
        expect([`Niepoprawny JSON: linia 1, kolumna ${column}.`, 'Niepoprawny JSON.']).toContain(
          r.message,
        );
    }
  });

  it('returns null when there is no position', () => {
    expect(extractPosition('Unexpected end of JSON input', '{')).toBeNull();
  });
});

describe('readJsonFile', () => {
  it('reads a .JSON file', async () => {
    const file = new File(['{"a":1}'], 'a.JSON');
    expect(await readJsonFile(file)).toEqual({ ok: true, text: '{"a":1}' });
  });

  it('accepts a file of exactly the limit', async () => {
    const file = new File([new Uint8Array(MAX_JSON_FILE_BYTES)], 'a.json');
    expect((await readJsonFile(file)).ok).toBe(true);
  });

  it('rejects another extension', async () => {
    expect(await readJsonFile(new File(['{}'], 'a.txt'))).toEqual({ ok: false, message: BAD_FILE });
  });

  it('rejects a file over the limit', async () => {
    const big = new File([new Uint8Array(MAX_JSON_FILE_BYTES + 1)], 'a.json');
    expect(await readJsonFile(big)).toEqual({ ok: false, message: BAD_FILE });
  });
});
