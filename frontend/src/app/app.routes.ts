import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/auth.guard';
import { ImportPage } from './features/import/import-page';
import { LoginPage } from './features/login/login-page';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'import' },
  { path: 'login', title: 'Logowanie', component: LoginPage, canActivate: [guestGuard] },
  { path: 'import', title: 'Import', component: ImportPage, canActivate: [authGuard] },
  {
    path: 'result/:id',
    title: 'Wynik',
    canActivate: [authGuard],
    loadComponent: () => import('./features/result/result-page').then((m) => m.ResultPage),
  },
  { path: '**', redirectTo: 'import' },
];
