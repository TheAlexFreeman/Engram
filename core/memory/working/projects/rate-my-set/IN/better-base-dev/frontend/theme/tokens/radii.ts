import { defineTokens } from '@chakra-ui/react';

export const radii = defineTokens.radii({
  // CV3M TODO: Designs and dev get on the same page and get all these defined, etc.
  none: { value: '0' },
  '2xs': { value: '0.0625rem' },
  xs: { value: '0.125rem' },
  sm: { value: '0.25rem' },
  base: { value: '0.375rem' },
  md: { value: '0.5rem' },
  lg: { value: '1rem' },
  xl: { value: '1.5rem' },
  '2xl': { value: '2.5rem' },
  '3xl': { value: '4rem' },
  '4xl': { value: '5rem' },
  full: { value: '9999px' },
});
