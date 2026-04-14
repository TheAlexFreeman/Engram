import { Box, Stack, chakra } from '@chakra-ui/react';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import PasswordRulesDisplay from '@/components/forms/display/PasswordRulesDisplay';
import PasswordField from '@/components/forms/fields/PasswordField';
import { isValidPassword } from '@/components/forms/validation/passwords';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import changePasswordService from '@/services/changePassword';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

type FormValues = {
  previousPassword: string;
  newPassword: string;
};

export default function UserEditPasswordForm() {
  const formContext = useForm<{
    previousPassword: string;
    newPassword: string;
  }>({
    defaultValues: {
      previousPassword: '',
      newPassword: '',
    },
  });

  const {
    handleSubmit,
    control,
    setFocus,
    reset,
    formState: { isSubmitting },
  } = formContext;

  const { BackendErrorsDisplay, errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>(
    { control },
  );

  const onSubmit = async (data: FormValues) => {
    const request = changePasswordService.changePassword({
      ...data,
      newPasswordConfirm: data.newPassword,
    });
    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      toaster.create({
        title: 'Updated password',
        description: `Your password has been updated successfully.`,
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });
      reset();
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

  return (
    <FormProvider {...formContext}>
      <chakra.form onSubmit={handleSubmit(onSubmit, onError)} width="100%">
        <Stack
          mb={6}
          gap={6}
          css={{
            // If this element has focus within, then display the password rules.
            '&:focus-within .password-rules': {
              display: 'block',
            },
            // Also, if this element has at least one `input` that does not have its
            // placeholder shown, then display the password rules.
            '&:has(input:not(:placeholder-shown)) .password-rules': {
              display: 'block',
            },
          }}
        >
          <PasswordField name={'previousPassword'} label={'Current Password'} required />
          <PasswordField
            name={'newPassword'}
            label={'New Password'}
            required
            slotProps={{
              register: {
                minLength: {
                  value: 9,
                  message: 'Passwords must be at least 9 characters long.',
                },
                validate: {
                  passesRules: (v) => isValidPassword(v) || 'Password does not meet requirements.',
                },
              },
              input: {
                minLength: 9,
              },
            }}
          />
          <Box alignSelf="flex-start" display="none" className="password-rules">
            <PasswordRulesDisplay fieldName="newPassword" />
          </Box>
        </Stack>

        <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
        <Button size={'sm'} type="submit" disabled={isSubmitting} loading={isSubmitting}>
          Save
        </Button>
      </chakra.form>
    </FormProvider>
  );
}
