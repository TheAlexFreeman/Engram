import { useCallback, useEffect, useRef, useState } from 'react';

import { Box, Container, Spinner, chakra } from '@chakra-ui/react';
import { createFileRoute, redirect } from '@tanstack/react-router';
import { useAtom } from 'jotai';
import { FormProvider, useForm } from 'react-hook-form';

import { setCsrfToken } from '@/api/csrf';
import { apiRequest } from '@/api/request';
import { InitialData } from '@/api/types/initialData';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

export const Route = createFileRoute('/auth/verify-email/confirm/$uidb64/$secretToken/')({
  loader: verifyEmailConfirmLoader,
  component: VerifyEmailConfirm,
});

function verifyEmailConfirmLoader() {
  const initialValues = store.get(initialDataAtom);
  const data = initialValues.extra.verifyEmailConfirm as VerifyEmailBackendProvidedPageData | null;

  if (data == null || !data.isValid) {
    throw redirect({ from: Route.fullPath, to: 'invalid' });
  }

  return data;
}

export type VerifyEmailBackendProvidedPageDataForValid = {
  uidb64: string;
  secretToken: string;
  isValid: true;
  canRequestAnotherLink: boolean;
};

export type VerifyEmailBackendProvidedPageDataForInvalid = {
  uidb64: string;
  secretToken: string;
  isValid: false;
  canRequestAnotherLink: boolean;
  errorCode: string;
  errorMessage: string;
};

export type VerifyEmailBackendProvidedPageData =
  | VerifyEmailBackendProvidedPageDataForValid
  | VerifyEmailBackendProvidedPageDataForInvalid;

type FormValues = Record<string, never>;

function VerifyEmailConfirm() {
  const { uidb64, secretToken } = Route.useLoaderData();

  const [isLoading] = useState<boolean>(true);
  const inProgressRef = useRef<{ action: 'confirming' | '' }>({ action: '' });

  const formContext = useForm<FormValues>({
    defaultValues: {},
  });
  const { handleSubmit, control } = formContext;
  const navigate = Route.useNavigate();

  const [initialData, setInitialData] = useAtom(initialDataAtom);
  const initiallyLoggedIn = initialData.user.isAuthenticated;

  const { errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>({ control });

  const onSubmit = useCallback(
    async (data: FormValues) => {
      if (inProgressRef.current?.action) return;

      const request = apiRequest('POST', '/api/auth/verify-email/confirm', {
        json: {
          ...data,
          uidb64,
          secretToken,
        },
      }) as Promise<InitialData>;

      try {
        inProgressRef.current.action = 'confirming';

        const wrapped = await errorWrappedRequest(request);
        if (!wrapped.hasError) {
          const responseData = wrapped.result;
          setCsrfToken(responseData.csrfToken);
          const justLoggedIn = responseData.user.isAuthenticated;
          const justLoggedOut = initiallyLoggedIn && !responseData.user.isAuthenticated;
          setInitialData(responseData, { justLoggedIn, justLoggedOut });

          void navigate({ to: '/auth/verify-email/confirm/success', viewTransition: true });
        } else {
          void navigate({ from: Route.fullPath, to: 'invalid', viewTransition: true });
        }
      } finally {
        inProgressRef.current.action = '';
      }
    },
    [secretToken, uidb64, errorWrappedRequest, initiallyLoggedIn, setInitialData, navigate],
  );

  useEffect(() => {
    void handleSubmit(onSubmit)();
  }, [handleSubmit, onSubmit]);

  return (
    <Container as="main" mt="2" centerContent>
      {isLoading && <Spinner />}
      <Box display="none">
        <FormProvider {...formContext}>
          <chakra.form onSubmit={handleSubmit(onSubmit)} width="100%"></chakra.form>
        </FormProvider>
      </Box>
    </Container>
  );
}
