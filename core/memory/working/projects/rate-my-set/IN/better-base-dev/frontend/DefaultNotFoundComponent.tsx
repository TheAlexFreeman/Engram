import { useMemo } from 'react';

import { Box, Link, Spacer, Text, VStack } from '@chakra-ui/react';

import dotsUrl from '@/assets/illustrations/Dots.svg';
import ellipseUrl from '@/assets/illustrations/Ellipse1.svg';
import { Button } from '@/components/ui/button';

export default function DefaultNotFoundComponent() {
  const backgroundProps = useMemo(
    () => ({
      w: '100%',
      backgroundImage: `url("${dotsUrl}")`,
      backgroundRepeat: 'no-repeat',
      minH: '100vh',
    }),
    [],
  );

  const stackProps = useMemo(
    () => ({
      gap: '2',
      maxW: '450px',
      py: '20',
      margin: 'auto',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
    }),
    [],
  );

  const mainTextProps = useMemo(
    () => ({
      fontSize: '116px',
      fontWeight: '600',
      bgClip: 'text',
      bgGradient: 'linear(#7772FF, #434099, rgba(31, 28, 104, 0.72))',
    }),
    [],
  );

  return (
    <Box {...backgroundProps}>
      <VStack {...stackProps}>
        <Text {...mainTextProps}>404</Text>
        <Text textStyle="h2" mt="-8">
          Page Not Found
        </Text>
        <VStack alignItems="inherit">
          <Text textStyle="body1">
            Looks like this page was moved, deleted, or maybe...
            <br />
            never even existed.
          </Text>
          <Spacer />
          <Link href="/">
            <Button p="2">Back to home</Button>
          </Link>
        </VStack>
        <Box bgImage={`url("${ellipseUrl}")`} w="287px" h="18px" ml="-16" mt="4" />
      </VStack>
    </Box>
  );
}
