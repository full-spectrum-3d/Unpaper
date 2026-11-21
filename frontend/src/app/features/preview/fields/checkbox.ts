import { Component } from '@angular/core';
import { FieldTooltip } from '../../../shared/ui/field-tooltip/field-tooltip';
import { FieldBase } from './field-base';
import { FieldLabel } from './field-label';

@Component({
  selector: 'app-checkbox-field',
  imports: [FieldLabel, FieldTooltip],
  template: `
    @if (field().options?.length) {
      <fieldset
        class="m-0 p-0 border-0"
        [attr.aria-labelledby]="id() + '-label'"
        [attr.aria-describedby]="describedBy()"
      >
        <app-field-label
          [label]="label()"
          [labelId]="id() + '-label'"
          [hidden]="!hasTitle()"
          [tooltip]="tooltip()"
          [tag]="tag()"
          [required]="required()"
          [announceRequired]="true"
        />
        @if (hasDescription()) {
          <div class="text-fg-muted mb-1.5" [id]="descId()" [innerHTML]="field().description"></div>
        }
        <!-- Options come from imported JSON: ids may repeat, so track by position. -->
        @for (o of field().options!; track $index) {
          <label class="flex items-center gap-2 py-1">
            <input
              type="checkbox"
              class="focus-ring"
              [checked]="value().includes(o.name)"
              [attr.aria-readonly]="readOnly() || null"
              [attr.aria-describedby]="describedBy()"
              [attr.aria-invalid]="error() ? 'true' : null"
              (click)="blockIfReadOnly($event)"
              (change)="toggle(o.name, $any($event.target).checked)"
            />
            {{ o.name }}
          </label>
        }
        @if (error(); as text) {
          <small [id]="errorId()" class="block text-danger"
            ><span aria-hidden="true">✕</span> {{ text }}</small
          >
        }
      </fieldset>
    } @else {
      <div class="flex flex-wrap items-center gap-x-2">
        <label class="flex items-center gap-2 py-1">
          <input
            type="checkbox"
            class="focus-ring"
            [attr.aria-describedby]="describedBy()"
            [attr.aria-invalid]="error() ? 'true' : null"
            [attr.aria-required]="required() || null"
            [attr.aria-readonly]="readOnly() || null"
            [checked]="value().includes(label())"
            (click)="blockIfReadOnly($event)"
            (change)="toggle(label(), $any($event.target).checked)"
          />
          {{ label() }}<span class="sr-only">{{ tag() ? ', ' + tag() : '' }}</span>
        </label>
        @if (required()) {
          <span class="text-danger -ml-1.5" aria-hidden="true">*</span>
        }
        @if (tooltip(); as text) {
          <app-field-tooltip [text]="text" [label]="label()" />
        }
        @if (tag(); as text) {
          <span class="ml-auto text-fg-muted text-label font-normal" aria-hidden="true">{{
            text
          }}</span>
        }
      </div>
      @if (hasDescription()) {
        <div class="text-fg-muted" [id]="descId()" [innerHTML]="field().description"></div>
      }
      @if (error(); as text) {
        <small [id]="errorId()" class="block text-danger"
          ><span aria-hidden="true">✕</span> {{ text }}</small
        >
      }
    }
  `,
  host: { class: 'block' },
})
export class CheckboxField extends FieldBase<string[]> {
  protected toggle(name: string, on: boolean) {
    this.set(on ? [...this.value(), name] : this.value().filter((n) => n !== name));
  }
}
