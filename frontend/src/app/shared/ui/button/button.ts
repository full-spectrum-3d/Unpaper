import { Component, computed, input } from '@angular/core';

const variants = {
  primary: 'bg-primary text-on-primary border-primary hover:bg-primary-hover',
  secondary: 'bg-surface text-primary border-primary hover:bg-primary-subtle',
  ghost: 'bg-transparent text-primary border-transparent hover:bg-primary-subtle',
};

@Component({
  selector: 'button[appButton]',
  template: '<ng-content />',
  host: { '[class]': 'classes()' },
})
export class Button {
  readonly variant = input<keyof typeof variants>('secondary');
  protected readonly classes = computed(
    () =>
      `border rounded-field px-[12px] py-field-y font-semibold text-body focus-ring disabled:opacity-50 disabled:cursor-not-allowed ${variants[this.variant()]}`,
  );
}
