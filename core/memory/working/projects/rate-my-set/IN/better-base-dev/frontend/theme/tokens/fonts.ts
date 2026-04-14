import { defineTokens } from '@chakra-ui/react';

export const fonts = defineTokens.fonts({
  // CV3M TODO: Double check on these values
  // CV3M TODO: Designs and dev get on the same page and get all these defined, etc.
  body: {
    value:
      'Public Sans, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"',
  },
  heading: {
    value:
      'Public Sans, Georgia, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", serif',
  },
  // CV3M TODO: Audit the monospace font? And add it here?
  mono: {
    value: 'SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace',
  },
});
