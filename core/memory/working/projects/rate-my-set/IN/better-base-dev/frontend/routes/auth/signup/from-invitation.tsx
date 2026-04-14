import { useEffect, useMemo } from 'react';

import { Box, HStack, Heading, VStack, chakra } from '@chakra-ui/react';
import { createFileRoute, redirect } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import type {
  FollowInvitationData,
  FollowInvitationDataWithoutError,
} from '@/routes/follow-invitation';

import PasswordRulesDisplay from '@/components/forms/display/PasswordRulesDisplay';
import EmailField from '@/components/forms/fields/EmailField';
import InputField from '@/components/forms/fields/InputField';
import PasswordField from '@/components/forms/fields/PasswordField';
import { isValidPassword } from '@/components/forms/validation/passwords';
import FullWithSideBackdrop from '@/components/layout/full/FullWithSideBackdrop';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authForInvitationsService from '@/services/authForInvitations';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

export const Route = createFileRoute('/auth/signup/from-invitation')({
  loader: signupFromInvitationLoader,
  component: SignupFromInvitation,
});

function signupFromInvitationLoader(): FollowInvitationDataWithoutError {
  const initialValues = store.get(initialDataAtom);
  const data = initialValues.extra.followInvitation as FollowInvitationData | null;

  if (data == null || data.hasError) {
    throw redirect({ to: '/follow-invitation/error' });
  }

  return data;
}

type FormValues = {
  email: string;
  firstName: string;
  lastName: string;
  password: string;
  passwordConfirm: string;
};

function SignupFromInvitation() {
  const initialData = useAtomValue(initialDataAtom);
  const initiallyLoggedIn = initialData.user.isAuthenticated;

  const loaderData = Route.useLoaderData();
  const { invitation } = loaderData;

  const nameSplit = (invitation.name || '').split(/\s+/);
  let initialFirst = '';
  let initialLast = '';
  if (nameSplit.length >= 2) {
    const namesCopy = Array.from(nameSplit);
    initialLast = namesCopy.pop() || '';
    initialFirst = namesCopy.join(' ') || '';
  } else if (nameSplit.length === 1) {
    initialFirst = nameSplit[0] || '';
  }

  const formContext = useForm<{
    email: string;
    firstName: string;
    lastName: string;
    password: string;
    passwordConfirm: string;
  }>({
    defaultValues: {
      email: invitation.email,
      firstName: initialFirst,
      lastName: initialLast,
      password: '',
      passwordConfirm: '',
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

  const onSubmit = async (formValues: FormValues) => {
    const request = authForInvitationsService.signupFromInvitation(
      { invitation, ...formValues },
      { initiallyLoggedIn },
    );
    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      const { justLoggedIn } = wrapped.result[1];

      if (justLoggedIn) {
        toaster.create({
          title: 'Successfully Signed Up',
          description: `Successfully signed up and joined ${invitation.teamDisplayName}.`,
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });
        void navigate({
          to: '/accounts/$accountId/team',
          params: { accountId: invitation.account.id.toString() },
        });
      } else {
        void navigate({ to: '/auth/verify-email/sent', viewTransition: true });
      }
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

  const autofocusWhich = useMemo<'firstName' | 'lastName' | 'password'>(() => {
    return !initialFirst ? 'firstName' : !initialLast ? 'lastName' : 'password';
  }, [initialFirst, initialLast]);

  useEffect(() => {
    setFocus(autofocusWhich);
  }, [setFocus, autofocusWhich]);

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
                Please create an account to join <strong>{invitation.teamDisplayName}</strong> with{' '}
                <strong>{invitation.email}</strong>.
              </Heading>
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
                        isValidPassword(v) || 'Password does not meet requirements.',
                    },
                  },
                  input: {
                    minLength: 9,
                  },
                }}
              />
              <PasswordField
                name={'passwordConfirm'}
                label={'Confirm Password'}
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
          </VStack>
        </chakra.form>
      </FormProvider>
    </FullWithSideBackdrop>
  );
}
