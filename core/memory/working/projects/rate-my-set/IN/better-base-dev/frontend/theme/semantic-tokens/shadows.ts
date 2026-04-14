import { defineSemanticTokens } from '@chakra-ui/react';

export const shadows = defineSemanticTokens.shadows({
  // CV3M TODO: Align with Chakra here? Or?
  outline: {
    value: {
      // CV3M TODO: Separate light and dark here?
      // CV3M TODO: Migrate these to newer style opacity tokens?
      _light: '0px 0px 0px 3px rgba(51, 72, 247, 0.25)',
      _dark: '0px 0px 0px 3px rgba(51, 72, 247, 0.25)',
    },
  },
  level1: {
    value: {
      // CV3M TODO: Separate light and dark here?
      // CV3M TODO: Migrate these to newer style opacity tokens?
      _light: '0px 0px 15px 0px rgba(31, 44, 147, 0.06)',
      _dark: '0px 0px 15px 0px rgba(31, 44, 147, 0.06)',
    },
  },
  level2: {
    value: {
      // CV3M TODO: Separate light and dark here?
      // CV3M TODO: Migrate these to newer style opacity tokens?
      _light: '0px 0px 17px 0px rgba(31, 44, 147, 0.12)',
      _dark: '0px 0px 17px 0px rgba(31, 44, 147, 0.12)',
    },
  },
  level3: {
    value: {
      // CV3M TODO: Separate light and dark here?
      // CV3M TODO: Migrate these to newer style opacity tokens?
      _light: '0px 0px 20px 0px rgba(31, 44, 147, 0.20)',
      _dark: '0px 0px 20px 0px rgba(31, 44, 147, 0.20)',
    },
  },
  dropdownBg: {
    value: {
      // CV3M TODO: Separate light and dark here?
      // CV3M TODO: Migrate these to newer style opacity tokens?
      _light: '0px 4px 20px 0px rgba(52, 58, 110, 0.10)',
      _dark: '0px 4px 20px 0px rgba(52, 58, 110, 0.10)',
    },
  },
  modalBg: {
    value: {
      // CV3M TODO: Separate light and dark here?
      // CV3M TODO: Migrate these to newer style opacity tokens?
      _light: '0px 0px 50px 0px rgba(31, 44, 147, 0.15)',
      _dark: '0px 0px 50px 0px rgba(31, 44, 147, 0.15)',
    },
  },
});
