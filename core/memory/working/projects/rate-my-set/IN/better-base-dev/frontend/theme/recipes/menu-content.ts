import { defineRecipe } from '@chakra-ui/react';

export const menuContentRecipe = defineRecipe({
  base: {
    p: 0,
  },
  variants: {
    radius: {
      rounded: {
        borderRadius: 24,
      },
      angled: {
        borderRadius: 4,
      },
    },
  },
  defaultVariants: {
    radius: 'rounded',
  },
});
