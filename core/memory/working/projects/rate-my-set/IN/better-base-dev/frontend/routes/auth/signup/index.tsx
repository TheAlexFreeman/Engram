import { Box, HStack, Heading, Link, VStack, chakra } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import MultiStepBarDisplay from '@/components/forms/display/MultiStepBarDisplay';
import PasswordRulesDisplay from '@/components/forms/display/PasswordRulesDisplay';
import EmailField from '@/components/forms/fields/EmailField';
import InputField from '@/components/forms/fields/InputField';
import PasswordField from '@/components/forms/fields/PasswordField';
import { isValidPassword } from '@/components/forms/validation/passwords';
import FullWithSideBackdrop from '@/components/layout/full/FullWithSideBackdrop';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authService from '@/services/auth';
import { initialDataAtom } from '@/state/auth';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/signup/')({
  component: Signup,
});

type FormValues = {
  email: string;
  firstName: string;
  lastName: string;
  password: string;
};

function Signup() {
  const initialData = useAtomValue(initialDataAtom);
  const initiallyLoggedIn = initialData.user.isAuthenticated;

  const formContext = useForm<{
    email: string;
    firstName: string;
    lastName: string;
    password: string;
  }>({
    defaultValues: {
      email: '',
      firstName: '',
      lastName: '',
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
    const request = authService.signup(
      { ...data, passwordConfirm: data.password },
      { initiallyLoggedIn },
    );
    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      const { user: signedUpUser } = wrapped.result[0];
      if (signedUpUser.isAuthenticated && !signedUpUser.emailIsVerified) {
        void navigate({ to: '/auth/signup/verify-email', viewTransition: true });
      } else {
        void navigate({ to: '/' });
      }
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

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
                Hello there!
              </Heading>
              <Heading as="h2" textStyle="body1">
                Please provide your name and email.
              </Heading>
              <MultiStepBarDisplay currentNum={1} totalNum={3} />
            </VStack>
            <HStack
              gap={4}
              wrap={{
                base: 'wrap',
                sm: 'nowrap',
              }}
            >
              <InputField name={'firstName'} label={'First Name'} required />
              <InputField name={'lastName'} label={'Last Name'} required />
            </HStack>
            <VStack>
              <EmailField name={'email'} label={'Email'} autocomplete="email" required />
            </VStack>
            <VStack gap={2}>
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
                        isValidPassword(v) || 'Please ensure your password meets the requirements:',
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
          </VStack>
          <VStack gap={6}>
            <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
            <Button
              disabled={isSubmitting}
              loading={isSubmitting}
              type="submit"
              variant="solidInverse"
              w="100%"
            >
              Next
            </Button>
            <Button asChild variant="plain" w="100%" textStyle="buttonM">
              <Link asChild>
                <RouterLink to="/auth/login" viewTransition>
                  I already have an account
                </RouterLink>
              </Link>
            </Button>
          </VStack>
        </chakra.form>
      </FormProvider>
    </FullWithSideBackdrop>
  );
}
