import { Box, HStack, Heading, Icon, Link, VStack } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';

import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

import type { VerifyEmailBackendProvidedPageDataForInvalid } from '.';

export const Route = createFileRoute('/auth/verify-email/confirm/$uidb64/$secretToken/invalid')({
  loader: verifyEmailConfirmInvalidLoader,
  component: VerifyEmailConfirmInvalid,
});

function verifyEmailConfirmInvalidLoader() {
  const initialValues = store.get(initialDataAtom);
  const result = initialValues.extra.verifyEmailConfirm || null;
  return result as VerifyEmailBackendProvidedPageDataForInvalid | null;
}

function VerifyEmailConfirmInvalid() {
  const { errorMessage, canRequestAnotherLink } = Route.useLoaderData() || {};

  return (
    <FullCentered>
      <FullCenteredPanel
        top={
          <VStack gap={4} mb="4" alignItems="stretch" width="100%">
            <HStack width="100%">
              <Box w="41px" h="32px">
                <MainLogo />
              </Box>
            </HStack>
            <VStack width="100%" alignItems="flex-start">
              <Heading as="h1" textStyle="body1" mt="8">
                {errorMessage == null
                  ? 'The email verification link you followed either has expired or is invalid. ' +
                    'Please request another link to verify your email.'
                  : errorMessage}
              </Heading>
            </VStack>
            <VStack gap="4" align="flex-start">
              {canRequestAnotherLink !== false && (
                <Button asChild variant="plain" pl="0">
                  <Link asChild>
                    <RouterLink to="/auth/verify-email/resend" viewTransition>
                      Request another link
                    </RouterLink>
                  </Link>
                </Button>
              )}
            </VStack>
          </VStack>
        }
        bottom={
          <Button asChild variant="plain" w="100%">
            <Link asChild>
              <RouterLink to="/auth/login" viewTransition>
                <Icon>
                  <ChevronLeftIcon />
                </Icon>
                Back to log in
              </RouterLink>
            </Link>
          </Button>
        }
      />
    </FullCentered>
  );
}
