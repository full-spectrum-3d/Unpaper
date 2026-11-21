import { Component } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, within } from 'storybook/test';
import { Badge, type FileStatus } from './badge/badge';
import { Button } from './button/button';
import { Card } from './card/card';
import { FileDrop } from './file-drop/file-drop';
import { Progress } from './progress/progress';
import { Table } from './table/table';
import { Topbar } from './topbar/topbar';

interface Row {
  name: string;
  size: string;
  status: FileStatus;
  error?: string;
}

@Component({
  selector: 'app-queue-harness',
  imports: [Topbar, FileDrop, Card, Table, Badge, Button, Progress],
  template: `
    <app-topbar appName="Formularze" userName="Jan Kowalski" />
    <main class="p-[16px] flex flex-col gap-[16px]">
      <h1 class="text-title font-semibold">Import formularzy</h1>
      <app-file-drop [maxSizeMb]="20" />
      <app-card>
        <h2 cardTitle>Kolejka</h2>
        <span cardActions class="flex items-center gap-[12px]">
          <span class="text-fg-muted">4 pliki · 1 gotowy · 1 błąd</span>
          <button appButton type="button" variant="primary">Pobierz wszystkie (ZIP)</button>
        </span>
        <table appTable>
          <thead>
            <tr>
              <th>Plik</th>
              <th>Rozmiar</th>
              <th>Status</th>
              <th>Akcje</th>
            </tr>
          </thead>
          <tbody>
            @for (r of rows; track r.name) {
              <tr>
                <td class="break-all">{{ r.name }}</td>
                <td>{{ r.size }}</td>
                <td>
                  <app-badge [status]="r.status" />
                  @if (r.status === 'processing') {
                    <app-progress [label]="'Przetwarzanie ' + r.name" class="mt-[4px]" />
                  }
                  @if (r.error) {
                    <div class="text-danger text-[12px]">{{ r.error }}</div>
                  }
                </td>
                <td>
                  <span class="flex gap-[8px]">
                    @if (r.status === 'done') {
                      <button appButton type="button" [attr.aria-label]="'Otwórz wynik ' + r.name">
                        Otwórz wynik
                      </button>
                    }
                    @if (r.status === 'error') {
                      <button appButton type="button" [attr.aria-label]="'Ponów ' + r.name">
                        Ponów
                      </button>
                    }
                    @if (r.status === 'pending' || r.status === 'error') {
                      <button appButton type="button" [attr.aria-label]="'Usuń ' + r.name">
                        Usuń
                      </button>
                    }
                  </span>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </app-card>
    </main>
  `,
})
class QueueHarness {
  protected readonly rows: Row[] = [
    { name: 'Deklaracja o wysokości opłaty.docx', size: '84 KB', status: 'done' },
    { name: 'Wniosek o dowód.pdf', size: '1,2 MB', status: 'processing' },
    { name: 'Skan wniosku.jpg', size: '2,4 MB', status: 'pending' },
    {
      name: 'formularz_z_bardzo_dluga_nazwa_bez_spacji_0123456789_0123456789_0123456789.jpe',
      size: '40 KB',
      status: 'error',
      error: 'Nieobsługiwane rozszerzenie. Wgraj PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.',
    },
  ];
}

const meta: Meta<QueueHarness> = {
  title: 'UI/Kolejka (kompozycja)',
  component: QueueHarness,
};
export default meta;
type Story = StoryObj<QueueHarness>;

const play: Story['play'] = async ({ canvasElement }) => {
  const c = within(canvasElement);
  expect(c.getAllByRole('row')).toHaveLength(5);
  for (const t of ['Gotowe', 'Przetwarzanie', 'Oczekuje', 'Błąd'])
    expect(c.getByText(t)).toBeVisible();
  expect(c.getByRole('button', { name: 'Usuń Skan wniosku.jpg' })).toBeVisible();
  // long file name does not overflow card
  const card = c.getByRole('table').closest('app-card') as HTMLElement;
  expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth);
};

export const Default: Story = { play };

export const Preview: Story = { globals: { theme: 'preview' }, play };
