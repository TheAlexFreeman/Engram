import { useEffect } from 'react';

import { Box, HStack, Heading, Link, VStack, chakra } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import EmailField from '@/components/forms/fields/EmailField';
import PasswordField from '@/components/forms/fields/PasswordField';
import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authService from '@/services/auth';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';
import { hardNavigate } from '@/utils/hardNavigation';

export const Route = createFileRoute('/auth/login/')({
  component: Login,
});

type FormValues = {
  email: string;
  password: string;
};

function Login() {
  const formContext = useForm<{
    email: string;
    password: string;
  }>({
    defaultValues: {
      email: '',
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

  const onSubmit = async (data: FormValues) => {
    const request = authService.login(data);
    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      hardNavigate({ to: '/' });
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

  useEffect(() => {
    setFocus('email');
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
                  <EmailField name={'email'} label={'Email'} autocomplete="email" required />
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
                <Button
                  asChild
                  variant="plain"
                  alignSelf="flex-end"
                  color="text.light"
                  textStyle="h6"
                >
                  <Link asChild>
                    <RouterLink to="/auth/reset-password" viewTransition>
                      Forgot password?
                    </RouterLink>
                  </Link>
                </Button>
              </VStack>
            </chakra.form>
          </FormProvider>
        }
        bottom={
          <Button asChild variant="plain" w="100%">
            <Link asChild>
              <RouterLink to="/auth/signup" viewTransition>
                Sign Up
              </RouterLink>
            </Link>
          </Button>
        }
      />
    </FullCentered>
  );
}
