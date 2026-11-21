export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`;
}

export function pluralPl(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  const last = n % 10;
  const lastTwo = n % 100;
  return last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14) ? few : many;
}

export function queueSummary(c: { total: number; done: number; error: number }): string {
  return [
    `${c.total} ${pluralPl(c.total, 'plik', 'pliki', 'plików')}`,
    `${c.done} ${pluralPl(c.done, 'gotowy', 'gotowe', 'gotowych')}`,
    `${c.error} ${pluralPl(c.error, 'błąd', 'błędy', 'błędów')}`,
  ].join(' · ');
}
