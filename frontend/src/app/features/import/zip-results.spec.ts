import { strFromU8, unzipSync } from 'fflate';
import { buildResultsZip, resultFileName } from './zip-results';

async function unzip(blob: Blob) {
  return unzipSync(new Uint8Array(await blob.arrayBuffer()));
}

describe('resultFileName', () => {
  it('replaces the last extension with .json', () => {
    expect(resultFileName('Deklaracja.docx')).toBe('Deklaracja.json');
    expect(resultFileName('a.b.pdf')).toBe('a.b.json');
  });
});

describe('buildResultsZip', () => {
  it('contains pretty JSON', async () => {
    const result = { a: 1, b: ['x'] };
    const files = await unzip(buildResultsZip([{ name: 'wniosek.pdf', result }]));
    const text = strFromU8(files['wniosek.json']);
    expect(JSON.parse(text)).toEqual(result);
    expect(text).toContain('\n  ');
  });

  it('dedupes names', async () => {
    const items = ['wniosek.pdf', 'wniosek.pdf', 'wniosek.png'].map((name) => ({ name, result: {} }));
    const files = await unzip(buildResultsZip(items));
    expect(Object.keys(files).sort()).toEqual(['wniosek (2).json', 'wniosek (3).json', 'wniosek.json']);
  });
});
