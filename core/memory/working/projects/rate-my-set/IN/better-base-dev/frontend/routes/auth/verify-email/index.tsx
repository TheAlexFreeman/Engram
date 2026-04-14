import { Box, HStack, Heading, Icon, Link, VStack, chakra } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import { apiRequest } from '@/api/request';
import { InitialData } from '@/api/types/initialData';
import EmailField from '@/components/forms/fields/EmailField';
import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/verify-email/')({
  component: VerifyEmailResend,
});

type FormValues = {
  email: string;
};

function VerifyEmailResend() {
  const formContext = useForm<{
    email: string;
  }>({
    defaultValues: {
      email: '',
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
    const request = apiRequest('POST', '/api/auth/verify-email/send', {
      json: data,
    }) as Promise<InitialData>;
    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      void navigate({ to: '/auth/verify-email/sent', viewTransition: true });
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
            <chakra.form onSubmit={handleSubmit(onSubmit, onError)} width="100%">
              <VStack gap={4} mb="4" alignItems="stretch">
                <HStack width="100%">
                  <Box w="41px" h="32px">
                    <MainLogo />
                  </Box>
                </HStack>
                <VStack width="100%" alignItems="flex-start">
                  <Heading as="h1" textStyle="h2">
                    Resend Verification Email
                  </Heading>
                  <Heading as="h2" textStyle="body1">
                    Please enter your email.
                  </Heading>
                </VStack>
                <VStack alignItems="stretch">
                  <EmailField name={'email'} label={'Email'} autocomplete="email" required />
                </VStack>
                <VStack gap={4} alignItems="flex-start">
                  <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
                  <Button
                    disabled={isSubmitting}
                    loading={isSubmitting}
                    type="submit"
                    variant="solidInverse"
                  >
                    Send
                  </Button>
                </VStack>
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
