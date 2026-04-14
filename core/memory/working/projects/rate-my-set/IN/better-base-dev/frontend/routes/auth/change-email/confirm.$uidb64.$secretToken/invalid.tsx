import { Box, HStack, Heading, Icon, VStack } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { initialDataAtom, userAtom } from '@/state/auth';
import store from '@/state/store';

import type { ChangeEmailBackendProvidedPageDataForInvalid } from '.';

export const Route = createFileRoute('/auth/change-email/confirm/$uidb64/$secretToken/invalid')({
  loader: changeEmailConfirmInvalidLoader,
  component: ChangeEmailConfirmInvalid,
});

async function changeEmailConfirmInvalidLoader() {
  const initialValues = store.get(initialDataAtom);
  const result = initialValues.extra.changeEmailConfirm || null;
  return result as ChangeEmailBackendProvidedPageDataForInvalid | null;
}

function ChangeEmailConfirmInvalid() {
  const { errorMessage } = Route.useLoaderData() || {};

  const user = useAtomValue(userAtom);
  const redirectTo = user.isAuthenticated ? '/settings/profile' : '/auth/login';
  const buttonText = user.isAuthenticated ? 'Back to profile' : 'Log in';

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
                  ? 'The email change link you followed either has expired or is invalid. ' +
                    'Please request another link from the place you originally requested ' +
                    'it at to change your email.'
                  : errorMessage}
              </Heading>
            </VStack>
          </VStack>
        }
        bottom={
          <Button asChild variant="ghost" w="100%">
            <RouterLink to={redirectTo} viewTransition>
              <Icon as={ChevronLeftIcon} />
              {buttonText}
            </RouterLink>
          </Button>
        }
      />
    </FullCentered>
  );
}
