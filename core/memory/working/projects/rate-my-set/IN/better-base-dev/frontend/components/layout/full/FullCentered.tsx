import { Box, Grid } from '@chakra-ui/react';

import HomeBackdrop from '../backgrounds/HomeBackdrop';

export default function FullCentered({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Box position="fixed" h="100vh" w="100vw">
        <HomeBackdrop
          size="full"
          h="100%"
          w="100%"
          bgSize="cover"
          bgRepeat="no-repeat"
          zIndex="hide"
        />
      </Box>
      <Grid
        as="main"
        bgColor="bg.body"
        minH="100vh"
        templateRows={`minmax(var(--gutter-size), 1fr) auto minmax(var(--gutter-size), 1fr)`}
        templateColumns="100%"
        justifyContent="center"
        justifyItems="center"
        alignContent="center"
        alignItems="center"
        css={{ '--gutter-size': 'spacing.6' }}
      >
        <Box display="none" css={{ '@supports (display: grid)': { display: 'block' } }} />
        {children}
        <Box display="none" css={{ '@supports (display: grid)': { display: 'block' } }} />
      </Grid>
    </>
  );
}
