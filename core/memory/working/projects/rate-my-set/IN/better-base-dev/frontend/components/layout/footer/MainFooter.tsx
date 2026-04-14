import { Box, Container, Link, Text } from '@chakra-ui/react';

export default function MainFooter() {
  return (
    <Box as="footer" py="3" px="3" mt="auto" bgColor="bg.level1" w="100%" minH="8">
      <Container maxW="sm">
        <Copyright />
      </Container>
    </Box>
  );
}

function Copyright() {
  return (
    <Text textStyle="body1">
      {'Copyright © '}
      <Link color="inherit" href="https://elyon.tech">
        Elyon Technologies
      </Link>{' '}
      {new Date().getFullYear()}
      {'.'}
    </Text>
  );
}
