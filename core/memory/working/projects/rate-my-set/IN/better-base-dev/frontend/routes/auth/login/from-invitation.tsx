import { useEffect } from 'react';

import { Box, HStack, Heading, VStack, chakra } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute, redirect } from '@tanstack/react-router';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import type {
  FollowInvitationData,
  FollowInvitationDataWithoutError,
} from '@/routes/follow-invitation';

import EmailField from '@/components/forms/fields/EmailField';
import PasswordField from '@/components/forms/fields/PasswordField';
import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authForInvitationsService from '@/services/authForInvitations';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';
import { getBestSingleErrorMessageFor } from '@/utils/errors';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/login/from-invitation')({
  loader: loginFromInvitationLoader,
  component: LoginFromInvitation,
});

function loginFromInvitationLoader(): FollowInvitationDataWithoutError {
  const initialValues = store.get(initialDataAtom);
  const data = initialValues.extra.followInvitation as FollowInvitationData | null;

  if (data == null || data.hasError) {
    throw redirect({ to: '/follow-invitation/error' });
  }

  return data;
}

type FormValues = {
  email: string;
  password: string;
};

function LoginFromInvitation() {
  const navigate = Route.useNavigate();

  const loaderData = Route.useLoaderData();
  const { invitation } = loaderData;

  const formContext = useForm<{
    email: string;
    password: string;
  }>({
    defaultValues: {
      email: invitation.email,
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

  const onSubmit = async (formValues: FormValues) => {
    const request = authForInvitationsService.loginFromInvitation({ invitation, ...formValues });
    const wrapped = await errorWrappedRequest(request);
    if (wrapped.hasError) {
      const errorMessage = getBestSingleErrorMessageFor(wrapped.error);
      toaster.create({
        title: 'Failed to Accept Invitation',
        description: errorMessage,
        type: 'error',
        duration: 10000,
        meta: { closable: true },
      });
    } else {
      toaster.create({
        title: 'Success',
        description: `Successfully logged in and joined ${invitation.teamDisplayName}.`,
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });
      void navigate({
        to: '/accounts/$accountId/team',
        params: { accountId: invitation.account.id.toString() },
      });
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

  useEffect(() => {
    setFocus('password');
  }, [setFocus]);

  return (
    <FullCentered>
      <FullCenteredPanel
        top={
          <FormProvider {...formContext}>
            <chakra.form onSubmit={handleSubmit(onSubmit, onError)} width="100%">
              <VStack gap={4} mb="4" alignItems="stretch">
                <HStack width="100%">
                  <Box w="41px" h="32px">
                    <MainLogo />
                  </Box>
                </HStack>
                <VStack width="100%" alignItems="flex-start">
                  <Heading as="h1" textStyle="h2">
                    Welcome
                  </Heading>
                </VStack>
                <VStack>
                  <EmailField
                    name={'email'}
                    label={'Email'}
                    autocomplete="email"
                    required
                    disabled
                  />
                </VStack>
                <VStack>
                  <PasswordField name={'password'} label={'Password'} required />
                </VStack>
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
                  Log in
                </Button>
                <Button asChild variant="ghost" alignSelf="flex-end" color="text.light">
                  <RouterLink to="/auth/reset-password" viewTransition>
                    Forgot password?
                  </RouterLink>
                </Button>
              </VStack>
            </chakra.form>
          </FormProvider>
        }
        bottom={
          <Button asChild variant="ghost" w="100%">
            <RouterLink to="/auth/signup" viewTransition>
              Sign Up
            </RouterLink>
          </Button>
        }
      />
    </FullCentered>
  );
}
