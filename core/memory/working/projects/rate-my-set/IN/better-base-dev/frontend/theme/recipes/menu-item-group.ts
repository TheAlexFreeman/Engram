import { defineSlotRecipe } from '@chakra-ui/react';

export const menuItemGroupRecipe = defineSlotRecipe({
  slots: ['title'],
  base: {
    title: { fontSize: 'xs', color: 'primary.text.lighter', pl: 4, pt: 3 },
  },
});
