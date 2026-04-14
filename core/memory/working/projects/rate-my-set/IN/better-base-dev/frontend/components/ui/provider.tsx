'use client';

import { ChakraProvider } from '@chakra-ui/react';
import { type SystemContext } from '@chakra-ui/react/styled-system';

import { ColorModeProvider, type ColorModeProviderProps } from './color-mode';

export interface ProviderProps extends Omit<ColorModeProviderProps, 'value'> {
  value: SystemContext;
}

export function Provider(props: ProviderProps) {
  const { value, ...colorModeProps } = props;
  return (
    <ChakraProvider value={value}>
      <ColorModeProvider {...colorModeProps} />
    </ChakraProvider>
  );
}
