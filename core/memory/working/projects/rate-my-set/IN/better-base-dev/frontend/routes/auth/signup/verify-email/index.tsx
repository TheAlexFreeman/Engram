import { useCallback, useEffect, useRef, useState } from 'react';

import { Box, HStack, Heading, Icon, Text, VStack, chakra } from '@chakra-ui/react';
import { ArrowRightIcon, ChevronRightIcon } from '@heroicons/react/20/solid';
import { createFileRoute, redirect } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import { InitialData } from '@/api/types/initialData';
import MultiStepBarDisplay from '@/components/forms/display/MultiStepBarDisplay';
import EditableEmailField from '@/components/forms/fields/EditableEmailField';
import FullWithSideBackdrop from '@/components/layout/full/FullWithSideBackdrop';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay, {
  wrapRequestWithErrorHandling,
} from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authService from '@/services/auth';
import { authUserAtom, initialDataAtom } from '@/state/auth';
import store from '@/state/store';
import { getBestSingleErrorMessageFor } from '@/utils/errors';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/signup/verify-email/')({
  loader: signUpVerifyEmailLoader,
  component: SignupVerifyEmail,
});

function signUpVerifyEmailLoader() {
  const data = store.get(initialDataAtom);

  if (data == null || !data.user || !data.user.isAuthenticated || data.user.emailIsVerified) {
    throw redirect({ to: '/' });
  }

  return data;
}

type FormValues = {
  email: string;
};

function SignupVerifyEmail() {
  const navigate = Route.useNavigate();

  const user = useAtomValue(authUserAtom);
  const { email: initialEmail } = user;

  const [isEditingEmail, setIsEditingEmail] = useState<boolean>(false);

  const formContext = useForm<{
    email: string;
  }>({
    defaultValues: {
      email: initialEmail,
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
      const request = authService.signupResendVerificationEmail({
        email: data.email || initialEmail,
      });
      const wrapped = await errorWrappedRequest(request);
      if (!wrapped.hasError) {
        const emailSentTo = wrapped.result.user.isAuthenticated
          ? wrapped.result.user.email
          : data.email || initialEmail;

        toaster.create({
          title: 'Email Sent',
          description: `Resent verification email to ${emailSentTo}.`,
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });
      }
    },
    [errorWrappedRequest, initialEmail],
  );

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

  const navigatePostVerification = useCallback(
    ({ inBackground }: { inBackground: boolean }) => {
      if (inBackground) {
        void navigate({ from: Route.fullPath, to: 'success' });
      } else {
        void navigate({ to: '/auth/signup/complete', viewTransition: true });
      }
    },
    [navigate],
  );

  const refreshRef = useRef<{ inProgress: boolean }>({ inProgress: false });
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const refresh = useCallback(
    async ({ inBackground }: { inBackground: boolean }) => {
      let data: InitialData | null | undefined = null;

      if (refreshRef.current.inProgress) return;

      try {
        refreshRef.current.inProgress = true;
        setIsRefreshing(true);

        const request = authService.refreshMe();
        const wrapped = await wrapRequestWithErrorHandling({ awaitable: request });

        if (wrapped.hasError) {
          const errorMessage = getBestSingleErrorMessageFor(wrapped.error);

          toaster.create({
            title: 'Failed to Refresh Verification Status',
            description: errorMessage,
            type: 'error',
            duration: 10000,
            meta: { closable: true },
          });
        } else {
          data = wrapped.result;
        }
      } finally {
        refreshRef.current.inProgress = false;
        setIsRefreshing(false);
      }

      if (data != null) {
        if (data.user.isAuthenticated && data.user.emailIsVerified) {
          if (!inBackground) {
            toaster.create({
              title: 'Verified',
              description: 'Your email has been verified.',
              type: 'success',
              duration: 7000,
              meta: { closable: true },
            });
          }
          navigatePostVerification({ inBackground });
        } else if (!inBackground) {
          const refreshedEmailValue = data.user.isAuthenticated ? data.user.email : initialEmail;
          toaster.create({
            title: 'Not Yet Verified',
            description: `Your email has not been verified yet (${refreshedEmailValue}).`,
            type: 'warning',
            duration: 10000,
            meta: { closable: true },
          });
        }
      }
    },
    [initialEmail, navigatePostVerification],
  );

  const handleRefreshClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      void refresh({ inBackground: false });
    },
    [refresh],
  );

  useEffect(() => {
    const originHere = window.location.origin;
    const channel = new BroadcastChannel('significantEvents');

    const onMessage = (event: MessageEvent): void => {
      const { data, origin } = event;

      if (origin !== originHere) return;
      if (typeof data !== 'object') return;

      if (data?.eventType === 'user.emailVerified') {
        void refresh({ inBackground: true });
      }
    };

    channel.addEventListener('message', onMessage, false);

    return () => {
      channel.removeEventListener('message', onMessage);
      channel.close();
    };
  }, [refresh]);

  return (
    <FullWithSideBackdrop>
      <FormProvider {...formContext}>
        <chakra.form onSubmit={handleSubmit(onSubmit, onError)} width="100%">
          <VStack gap={6} mb="6" alignItems="stretch">
            <HStack width="100%">
              <Box w="41px" h="32px">
                <MainLogo />
              </Box>
            </HStack>
            <VStack width="100%" alignItems="flex-start">
              <Heading as="h1" textStyle="h2">
                Verify your email
              </Heading>
              <Heading as="h2" textStyle="body1">
                Check your inbox! We sent you a link.
              </Heading>
              <MultiStepBarDisplay currentNum={2} totalNum={3} />
            </VStack>
            <VStack>
              <EditableEmailField
                name={'email'}
                label={'Email'}
                required
                isEditable={isEditingEmail}
                setIsEditable={setIsEditingEmail}
                labelForEdit="Edit email"
                labelForDoneEditing="Done editing email"
              />
            </VStack>
          </VStack>
          <VStack gap={32}>
            <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
            <Button
              disabled={isSubmitting}
              loading={isSubmitting}
              type="submit"
              variant="solidInverse"
              w="100%"
            >
              Resend Email
              <Icon>
                <ArrowRightIcon />
              </Icon>
            </Button>
            <VStack alignItems="center">
              <Text>I have verified on a different device or browser.</Text>
              <Button
                variant="ghost"
                onClick={handleRefreshClick}
                disabled={isRefreshing}
                loading={isRefreshing}
              >
                Continue
                <Icon>
                  <ChevronRightIcon />
                </Icon>
              </Button>
            </VStack>
          </VStack>
        </chakra.form>
      </FormProvider>
    </FullWithSideBackdrop>
  );
}
