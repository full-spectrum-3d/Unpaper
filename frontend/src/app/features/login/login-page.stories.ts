import { ActionsSubject } from '@ngrx/store';
import { of } from 'rxjs';
import { provideMockStore } from '@ngrx/store/testing';
import { applicationConfig, type Meta, type StoryObj } from '@storybook/angular-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';
import { AuthService } from '../../shared/api/services/auth.service';
import { AuthActions } from '../../store/auth/auth.actions';
import { AuthState, authFeatureKey, initialAuthState } from '../../store/auth/auth.reducer';
import { LoginPage } from './login-page';

const dispatched = fn();

function withAuth(auth: Partial<AuthState>, registrationEnabled = true) {
  return applicationConfig({
    providers: [
      {
        provide: AuthService,
        useValue: {
          authOptionsApiV1AuthOptionsGet: () => of({ registration_enabled: registrationEnabled }),
        },
      },
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
    expect(await within(canvasElement).findByRole('status')).toHaveTextContent(
      'Sesja wygasła, zaloguj się ponownie',
    );
  },
};

export const Register: Story = {
  decorators: [withAuth({})],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await userEvent.click(await c.findByRole('tab', { name: 'Rejestracja' }));
    expect(c.getByRole('tab', { name: 'Rejestracja' })).toHaveAttribute('aria-selected', 'true');
    await userEvent.click(c.getByRole('button', { name: 'Załóż konto' }));
    expect(c.getAllByText('Pole wymagane')).toHaveLength(3);

    await userEvent.type(c.getByLabelText('Login'), 'anna kowalska');
    await userEvent.type(c.getByLabelText('Hasło'), 'krotkie');
    await userEvent.type(c.getByLabelText('Powtórz hasło'), 'inne');
    await userEvent.click(c.getByRole('button', { name: 'Załóż konto' }));
    expect(c.getByText(/Login może zawierać tylko/)).toBeVisible();
    expect(c.getByText('Hasło musi mieć co najmniej 8 znaków')).toBeVisible();
    expect(c.getByText('Hasła nie są takie same')).toBeVisible();

    await userEvent.clear(c.getByLabelText('Login'));
    await userEvent.type(c.getByLabelText('Login'), 'anna.kowalska');
    await userEvent.clear(c.getByLabelText('Hasło'));
    await userEvent.type(c.getByLabelText('Hasło'), 'dlugie-haslo');
    await userEvent.clear(c.getByLabelText('Powtórz hasło'));
    await userEvent.type(c.getByLabelText('Powtórz hasło'), 'dlugie-haslo');
    await userEvent.click(c.getByRole('button', { name: 'Załóż konto' }));
    expect(dispatched).toHaveBeenCalledWith(
      AuthActions.register({ username: 'anna.kowalska', password: 'dlugie-haslo' }),
    );
  },
};

export const RegistrationDisabled: Story = {
  decorators: [withAuth({}, false)],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    expect(c.getByRole('button', { name: 'Zaloguj' })).toBeVisible();
    expect(c.queryByRole('tab', { name: 'Rejestracja' })).toBeNull();
  },
};

export const RevealPassword: Story = {
  decorators: [withAuth({})],
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    const input = c.getByLabelText('Hasło');
    expect(input).toHaveAttribute('type', 'password');
    await userEvent.click(c.getByRole('button', { name: 'Pokaż hasło' }));
    expect(input).toHaveAttribute('type', 'text');
    expect(c.getByRole('button', { name: 'Pokaż hasło' })).toHaveAttribute('aria-pressed', 'true');
  },
};
