import { Component, input } from '@angular/core';

@Component({
  selector: 'app-progress',
  template: '<div class="bar h-full w-1/3 rounded-full bg-primary"></div>',
  styles: `
    @keyframes slide {
      from {
        transform: translateX(-100%);
      }
      to {
        transform: translateX(300%);
      }
    }
    .bar {
      animation: slide 1.2s ease-in-out infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      .bar {
        animation: none;
      }
    }
  `,
  host: {
    role: 'progressbar',
    '[attr.aria-label]': 'label()',
    class: 'block h-[4px] overflow-hidden rounded-full bg-primary-subtle',
  },
})
export class Progress {
  readonly label = input.required<string>();
}
