import { Component, output } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';
import { FileDrop } from './file-drop';

@Component({
  selector: 'app-file-drop-harness',
  imports: [FileDrop],
  template: `<app-file-drop [maxSizeMb]="10" (filesSelected)="filesSelected.emit($event)" />`,
})
class FileDropHarness {
  readonly filesSelected = output<File[]>();
}

const meta: Meta<FileDropHarness> = {
  title: 'UI/FileDrop',
  component: FileDropHarness,
  args: { filesSelected: fn() },
};
export default meta;
type Story = StoryObj<FileDropHarness>;

export const Default: Story = {
  play: async ({ canvasElement, args }) => {
    const spy = args.filesSelected as ReturnType<typeof fn>;
    spy.mockClear();
    const c = within(canvasElement);
    const input = canvasElement.querySelector('input[type=file]') as HTMLInputElement;
    const a = new File(['a'], 'a.pdf', { type: 'application/pdf' });
    const b = new File(['b'], 'b.docx');
    const btn = c.getByRole('button', { name: 'Wybierz pliki' });
    expect(btn).toHaveAccessibleDescription(
      'PDF, DOC, DOCX, ODS, XLSX, JPG, PNG · do 10 MB · wiele plików naraz',
    );
    expect(input.multiple).toBe(true);
    expect(input.accept).toBe('.pdf,.doc,.docx,.ods,.xlsx,.jpg,.jpeg,.png');
    await userEvent.upload(input, [a, b]);
    expect(spy).toHaveBeenLastCalledWith([a, b]);
    // re-selecting the same file emits again
    await userEvent.upload(input, [a]);
    expect(spy).toHaveBeenCalledTimes(2);
    // drag state
    const zone = canvasElement.querySelector('app-file-drop')!;
    // fireEvent drops `files` from init.dataTransfer, so dispatch real DragEvents
    const drag = (type: string, dataTransfer: DataTransfer) =>
      zone.dispatchEvent(new DragEvent(type, { dataTransfer, bubbles: true, cancelable: true }));
    const dt = new DataTransfer();
    dt.items.add(b);
    drag('dragover', dt);
    // zoneless: host binding updates asynchronously
    await waitFor(() => expect(zone.hasAttribute('data-dragging')).toBe(true));
    drag('drop', dt);
    await waitFor(() => expect(zone.hasAttribute('data-dragging')).toBe(false));
    expect(spy).toHaveBeenLastCalledWith([b]);
    // drop without files emits nothing
    drag('drop', new DataTransfer());
    expect(spy).toHaveBeenCalledTimes(3);
  },
};

export const Preview: Story = { ...Default, globals: { theme: 'preview' } };
