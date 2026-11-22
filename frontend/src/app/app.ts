import { Component, ElementRef, Injector, afterNextRender, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Store } from '@ngrx/store';
import { filter, skip } from 'rxjs';
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

  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    const injector = inject(Injector);
    // After an in-app navigation focus the new page's <h1 tabindex="-1">, so screen readers start there
    // instead of on the link that was activated (WCAG 2.4.3). The first load keeps the browser default.
    inject(Router)
      .events.pipe(
        filter((e) => e instanceof NavigationEnd),
        skip(1),
        takeUntilDestroyed(),
      )
      .subscribe(() =>
        afterNextRender(() => host.querySelector<HTMLElement>('h1[tabindex="-1"]')?.focus(), {
          injector,
        }),
      );
  }

  protected logout(): void {
    this.store.dispatch(AuthActions.logout({ reason: 'manual' }));
  }
}
