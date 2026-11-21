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
