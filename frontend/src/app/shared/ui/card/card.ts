import { Component } from '@angular/core';

@Component({
  selector: 'app-card',
  template: `
    <div
      class="flex items-center gap-[10px] px-[10px] py-[8px] border-b border-border [&_[cardTitle]]:text-body [&_[cardTitle]]:font-semibold"
    >
      <ng-content select="[cardTitle]" />
      <div class="ml-auto flex gap-[8px]"><ng-content select="[cardActions]" /></div>
    </div>
    <ng-content />
  `,
  host: { class: 'block bg-surface border border-border rounded-card' },
})
export class Card {}
