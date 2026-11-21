import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, within } from 'storybook/test';
import nadplata from '../import/mock-forms/nadplata-podatku.json';
import { mockReport } from '../import/mock-report';
import { formatJson } from './json-lines';
import { asReport } from './report';
import { ReportView } from './report-view';

const ranges = formatJson(nadplata).ranges;

const meta: Meta<ReportView> = {
  title: 'Wynik/Raport',
  component: ReportView,
  args: { ranges, showInJson: fn() },
};
export default meta;
type Story = StoryObj<ReportView>;

export const ZRaportem: Story = {
  args: { report: asReport(mockReport(nadplata)) },
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    expect(c.getAllByRole('heading', { level: 2 })).toHaveLength(5);
    await userEvent.click(c.getByRole('button', { name: 'Pokaż w JSON: W07_CHOICE_OPTIONS' }));
    expect(args.showInJson).toHaveBeenCalledWith('tabs[0].questions[1].field.repeatingSectionGrid[0]');
    expect(c.getByText(/miejsce w szkicu, nie w wyniku/)).toBeVisible();
    expect(c.getByText('tekst z PDF')).toBeVisible();
  },
};

export const BezRaportu: Story = {
  args: { report: null },
  play: async ({ canvasElement }) => {
    expect(within(canvasElement).getByText('Raport niedostępny dla tego wyniku.')).toBeVisible();
  },
};

export const ZFallbackiem: Story = {
  args: {
    report: asReport({ llm: { model: null, fallback: true, fallbackReason: 'przekroczono limit czasu' }, warnings: 'x' }),
  },
  play: async ({ canvasElement }) => {
    expect(within(canvasElement).getByText(/szkic regułowy \(bez LLM\)/)).toBeVisible();
  },
};
