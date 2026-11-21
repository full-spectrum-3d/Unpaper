import { componentWrapperDecorator, type Preview } from '@storybook/angular-vite';
import '../src/styles.css';

const preview: Preview = {
  globalTypes: {
    theme: {
      description: 'Motyw',
      toolbar: {
        title: 'Motyw',
        icon: 'paintbrush',
        dynamicTitle: true,
        items: [
          { value: 'tool', title: 'Narzędzie' },
          { value: 'preview', title: 'Podgląd e-usługi' },
        ],
      },
    },
  },
  initialGlobals: { theme: 'tool' },
  decorators: [
    componentWrapperDecorator(
      (story) =>
        `<div [attr.data-theme]="sbTheme" class="bg-bg text-fg font-sans text-body p-section">${story}</div>`,
      ({ globals }) => ({ sbTheme: globals['theme'] ?? 'tool' }),
    ),
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },

    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: 'error',
    },
  },
};

export default preview;
