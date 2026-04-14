import { Box, HStack, VStack } from '@chakra-ui/react';

import { system } from '@/theme';

import HomeBackdrop from '../backgrounds/HomeBackdrop';

export default function FullWithSideBackdrop({ children }: { children: React.ReactNode }) {
  return (
    <Box
      as="main"
      css={{
        '--gutter-size': 'spacing.6',
        '--flex-basis-md': 'spacing.10',
        '--flex-basis-lg': 'spacing.40',
      }}
    >
      <HStack>
        <Box
          minH="100vh"
          flexBasis={'21.53%'}
          alignSelf="stretch"
          display={{ base: 'none', md: 'block' }}
        >
          <HomeBackdrop size="side" h="100%" w="100%" bgSize="cover" bgRepeat="no-repeat" />
        </Box>
        <Box
          css={{
            flexBasis: { md: 'var(--flex-basis-md)', lg: 'var(--flex-basis-lg)' },
            display: { base: 'none', md: 'block', lg: 'block' },
          }}
        />
        <Box
          // Set flexbox defaults (for if grid is not supported, see below).
          display="flex"
          flexDirection="column"
          justifyContent="flex-start"
          alignItems="center"
          mx="4"
          my="6"
          // Below medium width, expand the width of this box to 100%.
          width={{ base: '100%', md: 'auto' }}
          css={{
            // Grid overrides
            '@supports (display: grid)': {
              mx: '4',
              my: '0',
              display: 'grid',
              minH: '100vh',
              gridTemplateRows: `minmax(var(--gutter-size), 1fr) auto minmax(var(--gutter-size), 1fr)`,
              gridTemplateColumns: '100%',
              // Base defaults
              // Center the form if it's the only thing on the page.
              justifyContent: 'center',
              alignContent: 'center',
              justifyItems: 'center',
              alignItems: 'center',
              // Medium overrides
              [`@media screen and (${system.breakpoints.up('md')})`]: {
                justifyContent: 'auto',
                alignItems: 'stretch',
              },
            },
          }}
        >
          <Box display="none" css={{ '@supports (display: grid)': { display: 'block' } }} />
          <VStack
            alignSelf={{ base: 'auto', md: 'center' }}
            alignItems="center"
            maxW="60ch"
            width={{ base: '100%', md: '60ch' }}
          >
            {children}
          </VStack>
          <Box display="none" css={{ '@supports (display: grid)': { display: 'block' } }} />
        </Box>
      </HStack>
    </Box>
  );
}
