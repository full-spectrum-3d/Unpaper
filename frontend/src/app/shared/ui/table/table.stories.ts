import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';
import { Table } from './table';

@Component({
  selector: 'app-table-harness',
  imports: [Table],
  template: `
    <div>
      <table appTable>
        <thead>
          <tr>
            <th>Plik</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>deklaracja.pdf</td>
            <td>Gotowe</td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
})
class TableHarness {}

const meta: Meta<TableHarness> = { title: 'UI/Table', component: TableHarness };
export default meta;
type Story = StoryObj<TableHarness>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const css = (el: HTMLElement) => getComputedStyle(el);
    expect(css(c.getByRole('columnheader', { name: 'Plik' })).color).toBe('rgb(91, 100, 112)');
    expect(css(c.getByRole('cell', { name: /deklaracja/ })).borderBottomColor).toBe(
      'rgb(213, 219, 226)',
    );
    expect(css(c.getByRole('table')).width).toBe(css(c.getByRole('table').parentElement!).width);
  },
};

export const Preview: Story = { ...Default, globals: { theme: 'preview' } };
