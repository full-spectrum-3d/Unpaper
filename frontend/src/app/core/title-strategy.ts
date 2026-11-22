import { Injectable, inject } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterStateSnapshot, TitleStrategy } from '@angular/router';

export const APP_NAME = 'Cyfryzacja formularzy';

export const appTitle = (page: string): string => `${page} – ${APP_NAME}`;

/** "<route title> – <app name>", so every page has a unique, descriptive title (WCAG 2.4.2). */
@Injectable()
export class AppTitleStrategy extends TitleStrategy {
  private readonly title = inject(Title);

  override updateTitle(snapshot: RouterStateSnapshot): void {
    const page = this.buildTitle(snapshot);
    this.title.setTitle(page ? appTitle(page) : APP_NAME);
  }
}
