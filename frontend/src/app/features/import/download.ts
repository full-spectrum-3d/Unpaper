export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoking synchronously breaks downloads in Safari/Firefox.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadJson(result: unknown, fileName: string): void {
  downloadBlob(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }), fileName);
}
