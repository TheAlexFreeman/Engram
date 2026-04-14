import { Box, Separator, VStack } from '@chakra-ui/react';

export default function FullCenteredPanel({
  top,
  bottom,
}: {
  top: React.ReactNode;
  bottom: React.ReactNode;
}) {
  return (
    <Box
      // CV3M TODO: Did this work (same with below)?
      minW={{
        base: `min(calc(100% - (2 * (var(--space-base)))), var(--size-md))`,
        md: `min(calc(100% - (2 * (var(--space-md)))), var(--size-md))`,
      }}
      maxW="md"
      // CV3M TODO: Did this work (same with above)?
      css={{
        '--space-base': 'spacing.4',
        '--space-md': 'spacing.6',
        '--size-md': 'sizes.md',
      }}
    >
      <Box
        p={{ base: '4', md: '8' }}
        pos="relative"
        zIndex="base"
        bgImage="linear-gradient(24deg, {colors.whiteAlpha.700}, {colors.transparent})"
        _dark={{
          bgImage: 'linear-gradient(24deg, {colors.blackAlpha.700}, {colors.neutral.900})',
        }}
        borderWidth="2px"
        borderColor="bg.body"
        backdropFilter="blur(6px)"
        borderRadius="xl"
      >
        <VStack gap="4">
          {top}
          <Separator
            color="bg.body"
            borderColor="bg.body"
            opacity="1"
            // CV3M TODO: Did this work? And/or does it work?
            css={{ '--divider-border-width': '0.0625rem' }}
          />
          {bottom}
        </VStack>
      </Box>
    </Box>
  );
}
