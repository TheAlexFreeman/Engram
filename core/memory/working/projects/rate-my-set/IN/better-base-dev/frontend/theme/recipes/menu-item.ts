import { defineRecipe } from '@chakra-ui/react';

export const menuItemRecipe = defineRecipe({
  base: {
    width: '96%',
    cursor: 'pointer',
    height: '48px',
    p: 2,
    pl: 4,
    m: 1,
    textStyle: 'body2',
  },
  variants: {
    radius: {
      rounded: {
        borderRadius: 24,
      },
      angled: {
        borderRadius: 4,
      },
      none: {
        borderRadius: 0,
      },
    },
    itemPosition: {
      header: {
        bg: 'bg.level1',
        px: 3,
        py: 2,
        width: '100%',
        m: 0,
        borderRadius: 0,
        _hover: {
          bg: 'bg.level1',
        },
      },
      child: {
        _hover: {
          bg: 'primary.bg.light',
        },
      },
    },
    state: {
      normal: {
        color: 'text.main',
        _hover: {
          bg: 'primary.bg.light',
        },
      },
      header: {
        _hover: {
          bg: 'bg.level1',
        },
      },
      error: {
        color: 'fg.error',
        _hover: {
          bg: 'bg.error',
        },
        _active: {
          bg: 'bg.error',
        },
      },
    },
  },
  defaultVariants: {
    itemPosition: 'child',
    radius: 'rounded',
    state: 'normal',
  },
});
