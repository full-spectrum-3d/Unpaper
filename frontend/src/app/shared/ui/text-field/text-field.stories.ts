import { Component, signal } from '@angular/core';
import { form, FormField, required } from '@angular/forms/signals';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { expect, userEvent, within } from 'storybook/test';
import { TextField } from './text-field';

@Component({
  selector: 'app-text-field-harness',
  imports: [TextField],
  template: `
    <app-text-field label="Login" description="Konto techniczne" />
    <app-text-field label="Hasło" type="password" />
    <app-text-field label="Z błędem" error="Pole wymagane" />
  `,
})
class TextFieldHarness {}

@Component({
  selector: 'app-text-field-form-harness',
  imports: [TextField, FormField],
  template: `
    <app-text-field label="Login" [formField]="f.login" />
    <output data-testid="v">{{ f.login().value() }}</output>
  `,
})
class SignalFormHarness {
  protected readonly f = form(signal({ login: '' }), (p) => required(p.login));
}

const meta: Meta<TextFieldHarness> = { title: 'UI/TextField', component: TextFieldHarness };
export default meta;
type Story = StoryObj<TextFieldHarness>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const login = c.getByLabelText('Login');
    expect(login).toHaveAccessibleDescription('Konto techniczne');
    await userEvent.type(login, 'dev');
    expect(login).toHaveValue('dev');
    expect(c.getByLabelText('Hasło')).toHaveAttribute('type', 'password');
    const bad = c.getByLabelText('Z błędem');
    expect(bad).toHaveAttribute('aria-invalid', 'true');
    expect(bad).toHaveAccessibleDescription(/Pole wymagane/);
    expect(getComputedStyle(bad).borderColor).not.toBe(getComputedStyle(login).borderColor);
    await userEvent.tab(); // focus moves from Login to Hasło
    expect(getComputedStyle(document.activeElement as HTMLElement).outlineWidth).toBe('3px');
  },
};

export const Preview: Story = { ...Default, globals: { theme: 'preview' } };

export const SignalForm: StoryObj<SignalFormHarness> = {
  render: () => ({
    template: '<app-text-field-form-harness />',
    moduleMetadata: { imports: [SignalFormHarness] },
  }),
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await userEvent.type(c.getByLabelText('Login'), 'abc');
    expect(c.getByTestId('v')).toHaveTextContent('abc');
    expect(c.getByLabelText('Login')).toHaveAttribute('aria-required', 'true');
  },
};
