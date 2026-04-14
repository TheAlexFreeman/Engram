import { defineTokens } from '@chakra-ui/react';

export const lineHeights = defineTokens.lineHeights({
  // CV3M TODO: Double check on these values
  // CV3M TODO: Designs and dev get on the same page and get all these defined, etc.
  shorter: {
    value: 1.25,
  },
  short: {
    value: 1.375,
  },
  moderate: {
    value: 1.5,
  },
  tall: {
    value: 1.625,
  },
  taller: {
    value: 2,
  },
});
