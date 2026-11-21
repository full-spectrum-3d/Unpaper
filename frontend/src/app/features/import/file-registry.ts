import { Service } from '@angular/core';

/** Holds File objects outside the store (not serializable). */
@Service()
export class FileRegistry {
  private readonly files = new Map<string, File>();

  add(id: string, file: File): void {
    this.files.set(id, file);
  }

  get(id: string): File | undefined {
    return this.files.get(id);
  }

  delete(id: string): void {
    this.files.delete(id);
  }
}
