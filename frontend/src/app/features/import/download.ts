export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadJson(result: unknown, fileName: string): void {
  downloadBlob(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }), fileName);
}
