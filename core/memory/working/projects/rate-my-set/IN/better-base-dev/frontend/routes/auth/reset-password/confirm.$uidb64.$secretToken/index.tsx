import { Box, HStack, Heading, Icon, Link, VStack, chakra } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import { Link as RouterLink, createFileRoute, redirect } from '@tanstack/react-router';
import { useAtom } from 'jotai';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import { setCsrfToken } from '@/api/csrf';
import { apiRequest } from '@/api/request';
import { InitialData } from '@/api/types/initialData';
import PasswordRulesDisplay from '@/components/forms/display/PasswordRulesDisplay';
import PasswordField from '@/components/forms/fields/PasswordField';
import { isValidPassword } from '@/components/forms/validation/passwords';
import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/reset-password/confirm/$uidb64/$secretToken/')({
  loader: resetPasswordConfirmLoader,
  component: ResetPasswordConfirm,
});

async function resetPasswordConfirmLoader() {
  const initialValues = store.get(initialDataAtom);
  const data = initialValues.extra
    .resetPasswordConfirm as ResetPasswordBackendProvidedPageData | null;

  if (data == null || !data.isValid) {
    throw redirect({ from: Route.fullPath, to: 'invalid' });
  }

  return data;
}

export type ResetPasswordBackendProvidedPageDataForValid = {
  uidb64: string;
  secretToken: string;
  isValid: true;
  canRequestAnotherLink: boolean;
};

export type ResetPasswordBackendProvidedPageDataForInvalid = {
  uidb64: string;
  secretToken: string;
  isValid: false;
  canRequestAnotherLink: boolean;
  errorCode: string;
  errorMessage: string;
};

export type ResetPasswordBackendProvidedPageData =
  | ResetPasswordBackendProvidedPageDataForValid
  | ResetPasswordBackendProvidedPageDataForInvalid;

type FormValues = {
  password: string;
};

function ResetPasswordConfirm() {
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
  const navigate = Route.useNavigate();

  const { BackendErrorsDisplay, errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>(
    { control },
  );

  const onSubmit = async (data: FormValues) => {
    const request = apiRequest('POST', '/api/auth/reset-password/confirm', {
      json: {
        ...data,
        uidb64,
        secretToken,
      },
    }) as Promise<InitialData>;
    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      const responseData = wrapped.result;

      setCsrfToken(responseData.csrfToken);
      const justLoggedIn = responseData.user.isAuthenticated;
      const justLoggedOut = initiallyLoggedIn && !responseData.user.isAuthenticated;
      setInitialData(responseData, { justLoggedIn, justLoggedOut });

      toaster.create({
        title: 'Password Reset Successfully.',
        description: 'You have successfully reset your password.',
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });

      if (justLoggedIn) {
        void navigate({ to: '/' });
      } else {
        void navigate({ to: '/auth/login', viewTransition: true });
      }
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

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
                    Create Password
                  </Heading>
                  <Heading as="h2" textStyle="body1">
                    Please create a new password.
                  </Heading>
                </VStack>
                <PasswordField
                  name={'password'}
                  label={'Password'}
                  required
                  slotProps={{
                    register: {
                      minLength: {
                        value: 9,
                        message: 'Passwords must be at least 9 characters long.',
                      },
                      validate: {
                        passesRules: (v) =>
                          isValidPassword(v) || 'Password does not meet requirements.',
                      },
                    },
                    input: {
                      minLength: 9,
                    },
                  }}
                />
                <Box alignSelf="flex-start">
                  <PasswordRulesDisplay fieldName="password" />
                </Box>
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
                  Reset Password
                </Button>
              </VStack>
            </chakra.form>
          </FormProvider>
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
