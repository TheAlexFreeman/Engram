import { defineRecipe } from '@chakra-ui/react';

export const buttonRecipe = defineRecipe({
  variants: {
    variant: {
      solidInverse: {
        bg: 'bg.inverse',
        color: 'text.inverse',
        _hover: {
          bg: 'text.main',
          _disabled: {
            bg: 'bg.inverse',
          },
        },
        _active: {
          bg: 'text.main',
        },
        _disabled: {
          opacity: '0.6',
        },
      },
    },
  },
});
