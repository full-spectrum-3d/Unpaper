import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Store } from '@ngrx/store';
import { Topbar } from './shared/ui/topbar/topbar';
import { AuthActions } from './store/auth/auth.actions';
import { selectIsAuthenticated, selectUsername } from './store/auth/auth.selectors';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Topbar],
  selector: 'app-root',
  templateUrl: './app.html',
})
export class App {
  private readonly store = inject(Store);
  protected readonly isAuthenticated = this.store.selectSignal(selectIsAuthenticated);
  protected readonly username = this.store.selectSignal(selectUsername);

  protected logout(): void {
    this.store.dispatch(AuthActions.logout({ reason: 'manual' }));
  }
}
