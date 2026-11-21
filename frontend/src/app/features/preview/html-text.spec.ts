import { hasText } from './html-text';

describe('hasText', () => {
  it('detects text content', () => {
    expect(hasText('<html><head></head><body></body></html>')).toBe(false);
    expect(hasText('<p>tekst</p>')).toBe(true);
    expect(hasText('')).toBe(false);
    expect(hasText(undefined)).toBe(false);
  });
});
