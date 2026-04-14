import { defineTokens } from '@chakra-ui/react';

export const letterSpacings = defineTokens.letterSpacings({
  // CV3M TODO: Double check on these values
  // CV3M TODO: Designs and dev get on the same page and get all these defined, etc.
  tighter: {
    value: '-0.05em',
  },
  tight: {
    value: '-0.025em',
  },
  wide: {
    value: '0.025em',
  },
  wider: {
    value: '0.05em',
  },
  widest: {
    value: '0.1em',
  },
});
