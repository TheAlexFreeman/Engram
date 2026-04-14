import { Box, HStack, Heading, Link as NonRouterLink, VStack } from '@chakra-ui/react';
import { createFileRoute, redirect } from '@tanstack/react-router';

import FullWithSideBackdrop from '@/components/layout/full/FullWithSideBackdrop';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

export const Route = createFileRoute('/auth/signup/complete')({
  loader: signupCompleteLoader,
  component: SignupComplete,
});

async function signupCompleteLoader() {
  const data = store.get(initialDataAtom);

  if (data == null || !data.user || !data.user.isAuthenticated) {
    throw redirect({ to: '/' });
  }

  return data;
}

function SignupComplete() {
  return (
    <FullWithSideBackdrop>
      <VStack gap={6} mb="6" alignItems="stretch">
        <HStack width="100%">
          <Box w="41px" h="32px">
            <MainLogo />
          </Box>
        </HStack>
        <VStack width="100%" alignItems="flex-start" mb="6">
          <Heading as="h1" textStyle="h1">
            You made it
          </Heading>
          <Heading as="h2" textStyle="h2">
            Welcome to Better Base!
          </Heading>
        </VStack>
        <VStack gap={6}>
          <Button asChild variant="solidInverse" w="100%">
            <NonRouterLink href="/" _hover={{ textDecoration: 'none' }}>
              Let&apos;s go
            </NonRouterLink>
          </Button>
        </VStack>
      </VStack>
    </FullWithSideBackdrop>
  );
}
