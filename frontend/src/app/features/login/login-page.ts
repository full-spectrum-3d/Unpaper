import {
  afterNextRender,
  Component,
  effect,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
  viewChildren,
} from '@angular/core';
import { form, FormField, required } from '@angular/forms/signals';
import { Store } from '@ngrx/store';
import { Button } from '../../shared/ui/button/button';
import { Card } from '../../shared/ui/card/card';
import { TextField } from '../../shared/ui/text-field/text-field';
import { AuthActions } from '../../store/auth/auth.actions';
import {
  selectLoginError,
  selectLoginStatus,
  selectSessionExpired,
} from '../../store/auth/auth.selectors';

@Component({
  selector: 'app-login-page',
  imports: [Button, Card, TextField, FormField],
  templateUrl: './login-page.html',
  host: { class: 'flex min-h-screen items-center justify-center p-section' },
})
export class LoginPage {
  private readonly store = inject(Store);
  private readonly injector = inject(Injector);
  private readonly fields = viewChildren(TextField, { read: ElementRef });
  private readonly loginError = viewChild<ElementRef<HTMLElement>>('loginError');

  protected readonly status = this.store.selectSignal(selectLoginStatus);
  protected readonly error = this.store.selectSignal(selectLoginError);
  protected readonly sessionExpired = this.store.selectSignal(selectSessionExpired);
  protected readonly submitted = signal(false);

  protected readonly f = form(signal({ username: '', password: '' }), (p) => {
    required(p.username, { message: 'Pole wymagane' });
    required(p.password, { message: 'Pole wymagane' });
  });

  constructor() {
    effect(() => {
      if (this.status() === 'error') {
        afterNextRender(() => this.loginError()?.nativeElement.focus(), {
          injector: this.injector,
        });
      }
    });
  }

  protected message(field: typeof this.f.username): string | undefined {
    return this.submitted() ? field().errors()[0]?.message : undefined;
  }

  protected submit(event: Event): void {
    event.preventDefault();
    this.submitted.set(true);
    if (this.f().invalid()) {
      const i = [this.f.username, this.f.password].findIndex((x) => x().invalid());
      // Focus after render so aria-invalid/aria-describedby are already in the DOM.
      afterNextRender(() => this.fields()[i]?.nativeElement.querySelector('input')?.focus(), {
        injector: this.injector,
      });
      return;
    }
    const { username, password } = this.f().value();
    this.store.dispatch(AuthActions.login({ username, password }));
  }
}
