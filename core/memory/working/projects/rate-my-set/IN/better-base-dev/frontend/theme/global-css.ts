import { defineGlobalStyles } from '@chakra-ui/react';

export const globalCss = defineGlobalStyles({
  html: {
    colorPalette: 'purple',
  },
  // Get rid of the focus ring on links when it's only :focus (usually say from a user
  // clicking it) and not :focus-visible (say from a keyboard).
  'a:is(:focus, [data-focus]):not(:focus-visible)': {
    outline: 'none !important',
  },
});
