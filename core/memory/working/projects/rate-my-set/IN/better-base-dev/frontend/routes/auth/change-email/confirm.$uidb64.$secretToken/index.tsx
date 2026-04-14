import { useCallback } from 'react';

import { Box, HStack, Heading, Link, VStack, chakra } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute, redirect } from '@tanstack/react-router';
import { useAtom, useAtomValue } from 'jotai';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import type { InitialData } from '@/api/types/initialData';

import { setCsrfToken } from '@/api/csrf';
import { apiRequest } from '@/api/request';
import PasswordField from '@/components/forms/fields/PasswordField';
import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import { initialDataAtom, userAtom } from '@/state/auth';
import store from '@/state/store';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/change-email/confirm/$uidb64/$secretToken/')({
  loader: changeEmailConfirmLoader,
  component: ChangeEmailConfirm,
});

export type ChangeEmailBackendProvidedPageDataForValid = {
  uidb64: string;
  secretToken: string;
  isValid: true;
};

export type ChangeEmailBackendProvidedPageDataForInvalid = {
  uidb64: string;
  secretToken: string;
  isValid: false;
  errorCode: string;
  errorMessage: string;
};

export type ChangeEmailBackendProvidedPageData =
  | ChangeEmailBackendProvidedPageDataForValid
  | ChangeEmailBackendProvidedPageDataForInvalid;

async function changeEmailConfirmLoader() {
  const initialValues = store.get(initialDataAtom);
  const data = initialValues.extra.changeEmailConfirm as ChangeEmailBackendProvidedPageData | null;

  if (data == null || !data.isValid) {
    throw redirect({ from: Route.fullPath, to: 'invalid' });
  }

  return data;
}

type FormValues = {
  password: string;
};

function ChangeEmailConfirm() {
  const user = useAtomValue(userAtom);
  const redirectTo = user.isAuthenticated ? '/settings/profile' : '/auth/login';
  const navigate = Route.useNavigate();

  const [initialData, setInitialData] = useAtom(initialDataAtom);
  const initiallyLoggedIn = initialData.user.isAuthenticated;

  const { uidb64, secretToken } = Route.useLoaderData();

  const formContext = useForm<{
    password: string;
  }>({
    defaultValues: {
      password: '',
    },
  });
  const {
    handleSubmit,
    control,
    setFocus,
    formState: { isSubmitting },
  } = formContext;

  const { BackendErrorsDisplay, errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>(
    { control },
  );

  const onSubmit = useCallback(
    async (data: FormValues) => {
      const request = apiRequest('POST', '/api/auth/change-email/confirm', {
        json: {
          ...data,
          uidb64,
          secretToken,
        },
      }) as Promise<InitialData & { emailJustChangedTo: string }>;
      const wrapped = await errorWrappedRequest(request);
      if (!wrapped.hasError) {
        const responseData = wrapped.result;
        const emailJustChangedTo = responseData.emailJustChangedTo;

        setCsrfToken(responseData.csrfToken);
        const justLoggedIn = responseData.user.isAuthenticated;
        const justLoggedOut = initiallyLoggedIn && !responseData.user.isAuthenticated;
        setInitialData(responseData, { justLoggedIn, justLoggedOut });

        toaster.create({
          title: 'Email Changed.',
          description: `Successfully changed email to ${emailJustChangedTo}.`,
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });

        void navigate({ to: '/auth/change-email/confirm/success', viewTransition: true });
      }
    },
    [uidb64, secretToken, errorWrappedRequest, initiallyLoggedIn, setInitialData, navigate],
  );

  const onError = useCallback(
    async (errors: FieldErrors<FormValues>) => {
      scrollToFirstHookFormError({ errors, setFocus });
    },
    [setFocus],
  );

  return (
    <FullCentered>
      <FullCenteredPanel
        top={
          <FormProvider {...formContext}>
            <chakra.form onSubmit={handleSubmit(onSubmit, onError)} w="100%">
              <VStack gap={4} mb="4" alignItems="stretch">
                <HStack width="100%">
                  <Box w="41px" h="32px">
                    <MainLogo />
                  </Box>
                </HStack>
                <VStack width="100%" alignItems="flex-start">
                  <Heading as="h1" textStyle="h2">
                    Verify Email Change
                  </Heading>
                  <Heading as="h2" textStyle="body1">
                    Please enter your password below to confirm the requested email change.
                  </Heading>
                </VStack>
                <VStack>
                  <PasswordField name={'password'} label={'Password'} required />
                </VStack>
                <VStack gap={4}>
                  <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
                  <Button
                    disabled={isSubmitting}
                    loading={isSubmitting}
                    type="submit"
                    variant="solidInverse"
                    w="100%"
                  >
                    Confirm Email Change
                  </Button>
                </VStack>
              </VStack>
            </chakra.form>
          </FormProvider>
        }
        bottom={
          <Button asChild variant="plain" w="100%">
            <Link asChild>
              <RouterLink to={redirectTo} viewTransition>
                Cancel
              </RouterLink>
            </Link>
          </Button>
        }
      />
    </FullCentered>
  );
}
