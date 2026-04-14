'use client';

import type { IconButtonProps } from '@chakra-ui/react';

import * as React from 'react';

import { ClientOnly, IconButton, Skeleton } from '@chakra-ui/react';

import { useColorMode } from './hooks';
import { ColorModeIcon } from './icon';

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface ColorModeButtonProps extends Omit<IconButtonProps, 'aria-label'> {}

export const ColorModeButton = React.forwardRef<HTMLButtonElement, ColorModeButtonProps>(
  function ColorModeButton(props, ref) {
    const { toggleColorMode } = useColorMode();
    return (
      <ClientOnly fallback={<Skeleton boxSize="8" />}>
        <IconButton
          onClick={toggleColorMode}
          variant="ghost"
          aria-label="Toggle color mode"
          size="sm"
          ref={ref}
          {...props}
          css={{
            _icon: {
              width: '5',
              height: '5',
            },
          }}
        >
          <ColorModeIcon />
        </IconButton>
      </ClientOnly>
    );
  },
);
