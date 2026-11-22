import {
  afterNextRender,
  Component,
  computed,
  effect,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
  viewChildren,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  applyWhen,
  form,
  FormField,
  maxLength,
  minLength,
  pattern,
  required,
  validate,
} from '@angular/forms/signals';
import { Store } from '@ngrx/store';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../../shared/api/services/auth.service';
import { Button } from '../../shared/ui/button/button';
import { TextField } from '../../shared/ui/text-field/text-field';
import { AuthActions } from '../../store/auth/auth.actions';
import {
  selectLoginError,
  selectLoginStatus,
  selectSessionExpired,
} from '../../store/auth/auth.selectors';

type Mode = 'login' | 'register';

// Same rules as RegisterRequest in the API (backend/app/api/v1/auth.py).
const USERNAME_PATTERN = /^[A-Za-z0-9._-]+$/;
const LENGTH_MESSAGE = 'Login musi mieć od 3 do 50 znaków';

@Component({
  selector: 'app-login-page',
  imports: [Button, TextField, FormField],
  templateUrl: './login-page.html',
  host: { class: 'flex min-h-screen items-center justify-center bg-bg p-section' },
})
export class LoginPage {
  private readonly store = inject(Store);
  private readonly injector = inject(Injector);
  private readonly fields = viewChildren(TextField, { read: ElementRef });
  private readonly loginError = viewChild<ElementRef<HTMLElement>>('loginError');

  protected readonly tabs: { mode: Mode; label: string }[] = [
    { mode: 'login', label: 'Logowanie' },
    { mode: 'register', label: 'Rejestracja' },
  ];

  protected readonly status = this.store.selectSignal(selectLoginStatus);
  protected readonly error = this.store.selectSignal(selectLoginError);
  protected readonly sessionExpired = this.store.selectSignal(selectSessionExpired);
  protected readonly registrationEnabled = toSignal(
    inject(AuthService)
      .authOptionsApiV1AuthOptionsGet()
      .pipe(
        map((o) => o.registration_enabled),
        catchError(() => of(false)),
      ),
    { initialValue: false },
  );
  protected readonly mode = signal<Mode>('login');
  protected readonly isRegister = computed(() => this.mode() === 'register');
  protected readonly submitted = signal(false);
  protected readonly statusText = signal('');
  /** Mode of the last request: an error from logging in is not shown on the register tab. */
  private readonly sentFrom = signal<Mode | null>(null);

  protected readonly visibleError = computed(() => {
    const sent = this.sentFrom();
    return this.status() === 'error' && (sent === null || sent === this.mode())
      ? this.error()
      : null;
  });
  protected readonly submitLabel = computed(() => {
    const pending = this.status() === 'pending';
    if (this.isRegister()) return pending ? 'Zakładanie konta…' : 'Załóż konto';
    return pending ? 'Logowanie…' : 'Zaloguj';
  });

  protected readonly f = form(signal({ username: '', password: '', confirm: '' }), (p) => {
    required(p.username, { message: 'Pole wymagane' });
    required(p.password, { message: 'Pole wymagane' });
    applyWhen(
      p,
      () => this.isRegister(),
      (r) => {
        required(r.confirm, { message: 'Pole wymagane' });
        minLength(r.username, 3, { message: LENGTH_MESSAGE });
        maxLength(r.username, 50, { message: LENGTH_MESSAGE });
        pattern(r.username, USERNAME_PATTERN, {
          message: 'Login może zawierać tylko litery, cyfry oraz . _ -',
        });
        minLength(r.password, 8, { message: 'Hasło musi mieć co najmniej 8 znaków' });
        maxLength(r.password, 128, { message: 'Hasło może mieć najwyżej 128 znaków' });
        validate(r.confirm, ({ value, valueOf }) =>
          value() && value() !== valueOf(r.password)
            ? { kind: 'mismatch', message: 'Hasła nie są takie same' }
            : null,
        );
      },
    );
  });

  constructor() {
    effect(() => {
      const text = this.sessionExpired() ? 'Sesja wygasła, zaloguj się ponownie' : '';
      afterNextRender(() => this.statusText.set(text), { injector: this.injector });
    });
    effect(() => {
      if (this.visibleError()) {
        afterNextRender(() => this.loginError()?.nativeElement.focus(), {
          injector: this.injector,
        });
      }
    });
  }

  protected setMode(mode: Mode): void {
    if (mode === this.mode()) return;
    this.mode.set(mode);
    this.submitted.set(false);
  }

  /** Arrow keys and the link under the form both flip to the other tab. */
  protected switchTab(): void {
    this.setMode(this.isRegister() ? 'login' : 'register');
    afterNextRender(() => document.getElementById(`tab-${this.mode()}`)?.focus(), {
      injector: this.injector,
    });
  }

  protected message(field: typeof this.f.username): string | undefined {
    return this.submitted() ? field().errors()[0]?.message : undefined;
  }

  protected submit(event: Event): void {
    event.preventDefault();
    this.submitted.set(true);
    const order = [this.f.username, this.f.password, this.f.confirm];
    const invalid = order.findIndex((x) => x().invalid());
    if (invalid !== -1) {
      // Focus after render so aria-invalid/aria-describedby are already in the DOM.
      afterNextRender(() => this.fields()[invalid]?.nativeElement.querySelector('input')?.focus(), {
        injector: this.injector,
      });
      return;
    }
    const { username, password } = this.f().value();
    this.sentFrom.set(this.mode());
    this.store.dispatch(
      this.isRegister()
        ? AuthActions.register({ username, password })
        : AuthActions.login({ username, password }),
    );
  }
}
