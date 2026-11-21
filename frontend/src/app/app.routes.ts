import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/auth.guard';
import { ImportPage } from './features/import/import-page';
import { LoginPage } from './features/login/login-page';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'import' },
  { path: 'login', component: LoginPage, canActivate: [guestGuard] },
  { path: 'import', component: ImportPage, canActivate: [authGuard] },
  { path: '**', redirectTo: 'import' },
];
