import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-topbar',
  template: `
    <header
      class="bg-topbar text-on-topbar min-h-[44px] flex flex-wrap items-center gap-x-[20px] gap-y-[4px] px-[16px] py-[4px]"
    >
      <ng-content select="[brand]">
        <span class="font-bold">{{ appName() }}</span>
      </ng-content>
      <nav
        aria-label="Główna"
        class="flex gap-[16px] [&_a]:text-on-topbar [&_a]:opacity-75 [&_a:hover]:opacity-100 [&_a]:focus-ring [&_a:focus-visible]:outline-on-topbar [&_a[aria-current=page]]:opacity-100 [&_a[aria-current=page]]:border-b-2 [&_a[aria-current=page]]:border-on-topbar"
      >
        <ng-content />
      </nav>
      <div class="ml-auto flex items-center gap-[12px]">
        <span>{{ userName() }}</span>
        <button
          type="button"
          class="text-on-topbar border border-on-topbar rounded-field px-[12px] py-field-y text-body font-semibold hover:opacity-75 focus-ring focus-visible:outline-on-topbar"
          (click)="logout.emit()"
        >
          Wyloguj
        </button>
      </div>
    </header>
  `,
  host: { class: 'block' },
})
export class Topbar {
  readonly appName = input.required<string>();
  readonly userName = input.required<string>();
  readonly logout = output<void>();
}
