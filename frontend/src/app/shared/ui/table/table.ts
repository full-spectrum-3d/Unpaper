import { Component } from '@angular/core';

@Component({
  selector: 'table[appTable]',
  template: '<ng-content />',
  host: {
    class:
      'w-full border-collapse text-body ' +
      '[&_th]:text-left [&_th]:font-semibold [&_th]:text-fg-muted [&_th]:border-b [&_th]:border-border [&_th]:py-[7px] [&_th]:px-[10px] ' +
      '[&_td]:border-b [&_td]:border-border [&_td]:align-middle [&_td]:py-[7px] [&_td]:px-[10px] ' +
      '[&_tbody_tr:last-child_td]:border-b-0',
  },
})
export class Table {}
