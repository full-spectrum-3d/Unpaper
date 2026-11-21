import { TestBed } from '@angular/core/testing';
import { FileRegistry } from './file-registry';

describe('FileRegistry', () => {
  it('adds, gets and deletes files', () => {
    const registry = TestBed.inject(FileRegistry);
    const file = new File(['x'], 'a.pdf');
    registry.add('1', file);
    expect(registry.get('1')).toBe(file);
    registry.delete('1');
    expect(registry.get('1')).toBeUndefined();
  });

  it('clears everything', () => {
    const registry = TestBed.inject(FileRegistry);
    registry.add('1', new File(['x'], 'a.pdf'));
    registry.add('2', new File(['x'], 'b.pdf'));
    registry.clear();
    expect(registry.get('1')).toBeUndefined();
    expect(registry.get('2')).toBeUndefined();
  });
});

describe('FileRegistry passwords', () => {
  it('stores a password per file and drops it with the file', () => {
    const registry = TestBed.inject(FileRegistry);
    registry.add('1', new File(['x'], 'a.pdf'));
    registry.setPassword('1', 'tajne');
    expect(registry.password('1')).toBe('tajne');
    registry.deletePassword('1');
    expect(registry.password('1')).toBeUndefined();
    registry.setPassword('1', 'tajne');
    registry.delete('1');
    expect(registry.password('1')).toBeUndefined();
  });

  it('clear drops passwords too', () => {
    const registry = TestBed.inject(FileRegistry);
    registry.setPassword('1', 'tajne');
    registry.clear();
    expect(registry.password('1')).toBeUndefined();
  });
});
