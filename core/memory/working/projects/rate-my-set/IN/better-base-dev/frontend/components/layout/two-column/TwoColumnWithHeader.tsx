import { Grid, GridItem, GridProps, StackProps, VStack } from '@chakra-ui/react';

export default function TwoColumnWithHeader({
  left,
  right,
  header,
  stackProps,
  gridProps,
}: {
  left: React.ReactNode;
  right: React.ReactNode;
  header?: React.ReactNode;
  stackProps?: StackProps;
  gridProps?: GridProps;
}) {
  return (
    <VStack w="90%" gap={4} align="stretch" {...stackProps}>
      {header}
      <Grid
        minW={{
          base: `calc(100% - (2 * var(--chakra-spacing-4)))`,
          md: `calc(100% - (2 * var(--chakra-spacing-6)))`,
        }}
        templateAreas={{
          base: `
        "spacer1"
        "content1"
        "spacer2"
        "content2"
        "spacer3"
        `,
          md: `"spacer1 content1 spacer2 content2 spacer3"`,
        }}
        templateRows={{
          base: `0px auto var(--chakra-spacing-4) auto var(--chakra-spacing-4)`,
          md: 'auto',
        }}
        templateColumns={{
          base: '100%',
          md: `var(--chakra-spacing-14) 1fr var(--chakra-spacing-16) 1fr var(--chakra-spacing-16)`,
          lg: `var(--chakra-spacing-14) 1fr var(--chakra-spacing-32) 1fr var(--chakra-spacing-16)`,
          xl: `var(--chakra-spacing-14) 1fr var(--chakra-spacing-32) 1fr var(--chakra-spacing-32)`,
        }}
        {...gridProps}
      >
        <GridItem area="spacer1" />
        <GridItem area="content1">{left} </GridItem>
        <GridItem area="spacer2" />
        <GridItem area="content2">{right} </GridItem>
        <GridItem area="spacer3" />
      </Grid>
    </VStack>
  );
}
