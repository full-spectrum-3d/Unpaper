import { ActionsSubject } from '@ngrx/store';
import { provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';
import { AuthActions } from '../../store/auth/auth.actions';
import { AuthState, authFeatureKey, initialAuthState } from '../../store/auth/auth.reducer';
import { LoginPage } from './login-page';

const dispatched = fn();

function withAuth(auth: Partial<AuthState>) {
  return applicationConfig({
    providers: [
      provideMockStore({ initialState: { [authFeatureKey]: { ...initialAuthState, ...auth } } }),
      {
        provide: ActionsSubject,
        useFactory: () => {
          const s = new ActionsSubject();
          s.subscribe((a) => dispatched(a));
          return s;
        },
      },
    ],
  });
}

const meta: Meta<LoginPage> = {
  title: 'Ekrany/Logowanie',
  component: LoginPage,
  beforeEach: () => dispatched.mockClear(),
};
export default meta;
type Story = StoryObj<LoginPage>;

export const Default: Story = {
  decorators: [withAuth({})],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await userEvent.click(c.getByRole('button', { name: 'Zaloguj' }));
    expect(c.getAllByText('Pole wymagane')).toHaveLength(2);
    await waitFor(() => expect(document.activeElement).toBe(c.getByLabelText('Login')));
    expect(c.getByLabelText('Login')).toHaveAccessibleDescription(/Pole wymagane/);
    expect(c.getByLabelText('Login')).toHaveAttribute('aria-required', 'true');
    expect(c.getByLabelText('Hasło')).toHaveAttribute('aria-required', 'true');
    expect(dispatched).not.toHaveBeenCalledWith(expect.objectContaining({ username: 'dev' }));
    await userEvent.type(c.getByLabelText('Login'), 'dev');
    await userEvent.type(c.getByLabelText('Hasło'), 'secret');
    await userEvent.click(c.getByRole('button', { name: 'Zaloguj' }));
    expect(dispatched).toHaveBeenCalledWith(
      AuthActions.login({ username: 'dev', password: 'secret' }),
    );
  },
};

export const LoginError: Story = {
  decorators: [withAuth({ status: 'error', error: 'Nieprawidłowy login lub hasło' })],
  play: async ({ canvasElement }) => {
    const alert = within(canvasElement).getByRole('alert');
    expect(alert).toHaveTextContent('Nieprawidłowy login lub hasło');
    await waitFor(() => expect(document.activeElement).toBe(alert));
  },
};

export const Pending: Story = {
  decorators: [withAuth({ status: 'pending' })],
  play: async ({ canvasElement }) => {
    expect(within(canvasElement).getByRole('button', { name: 'Logowanie…' })).toBeDisabled();
  },
};

export const SessionExpired: Story = {
  decorators: [withAuth({ sessionExpired: true })],
  play: async ({ canvasElement }) => {
    expect(within(canvasElement).getByText('Sesja wygasła, zaloguj się ponownie')).toBeVisible();
  },
};
