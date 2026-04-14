import { useMemo } from 'react';

import { Icon, IconButton } from '@chakra-ui/react';
import { Moon as MoonIcon, Sun as SunIcon } from '@phosphor-icons/react';

import { useColorMode } from '@/components/ui/color-mode';

export default function ColorModeToggle() {
  const { colorMode, toggleColorMode } = useColorMode();

  const IconToUse = useMemo(() => {
    if (colorMode === 'dark') {
      return SunIcon;
    }
    return MoonIcon;
  }, [colorMode]);

  return (
    <IconButton
      onClick={toggleColorMode}
      aria-label="Toggle color mode"
      bgColor="transparent"
      _hover={{ bgColor: 'transparent' }}
      _active={{ bgColor: 'transparent' }}
      css={{
        '&:hover, &:active': {
          '& .colorModeIcon': {
            color: 'primary.bg.contrast',
          },
        },
      }}
    >
      <Icon color="primary.bg.main">
        <IconToUse weight="fill" className="colorModeIcon"></IconToUse>
      </Icon>
    </IconButton>
  );
}
