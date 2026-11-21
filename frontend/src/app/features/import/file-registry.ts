import { Service } from '@angular/core';

/** Holds File objects and document passwords outside the store (not serializable; passwords must not reach DevTools or sessionStorage). */
@Service()
export class FileRegistry {
  private readonly files = new Map<string, File>();
  private readonly passwords = new Map<string, string>();

  add(id: string, file: File): void {
    this.files.set(id, file);
  }

  get(id: string): File | undefined {
    return this.files.get(id);
  }

  setPassword(id: string, password: string): void {
    this.passwords.set(id, password);
  }

  password(id: string): string | undefined {
    return this.passwords.get(id);
  }

  deletePassword(id: string): void {
    this.passwords.delete(id);
  }

  delete(id: string): void {
    this.files.delete(id);
    this.passwords.delete(id);
  }

  clear(): void {
    this.files.clear();
    this.passwords.clear();
  }
}
