/** True when the HTML contains any text (empty `<html><head></head><body></body></html>` skeletons do not). */
export const hasText = (html: string | undefined): boolean =>
  !!html && new DOMParser().parseFromString(html, 'text/html').body.textContent!.trim() !== '';
