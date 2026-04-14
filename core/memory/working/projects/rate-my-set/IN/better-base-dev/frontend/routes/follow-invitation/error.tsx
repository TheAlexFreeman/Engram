import { Box, HStack, Heading, Icon, VStack } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';

import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

import type { FollowInvitationDataWithError } from '.';

export const Route = createFileRoute('/follow-invitation/error')({
  loader: followInvitationErrorLoader,
  component: FollowInvitationError,
});

export interface FollowInvitationErrorData {
  errorMessage: string;
  errorCode: string;
}

function followInvitationErrorLoader() {
  const initialValues = store.get(initialDataAtom);
  return (initialValues.extra.followInvitationError || {}) as FollowInvitationDataWithError &
    FollowInvitationErrorData;
}

function FollowInvitationError() {
  const data = Route.useLoaderData();
  const { errorMessage } = data;

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
                  ? 'Looks like that link has expired! Please request another invitation ' +
                    'from the person who invited you.'
                  : errorMessage}
              </Heading>
            </VStack>
            <VStack gap="4" align="flex-start">
              <Button asChild variant="ghost">
                <RouterLink to="/auth/login" viewTransition>
                  Log In
                </RouterLink>
              </Button>
            </VStack>
          </VStack>
        }
        bottom={
          <Button asChild variant="ghost" w="100%">
            <RouterLink to="/auth/signup" viewTransition>
              <Icon as={ChevronLeftIcon} />
              Sign Up
            </RouterLink>
          </Button>
        }
      />
    </FullCentered>
  );
}
