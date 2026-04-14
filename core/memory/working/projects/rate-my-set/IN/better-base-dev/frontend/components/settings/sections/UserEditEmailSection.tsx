import { useCallback, useMemo, useState } from 'react';

import { HStack, Icon, Text, VStack, chakra } from '@chakra-ui/react';
import ArrowPathIcon from '@heroicons/react/24/solid/ArrowPathIcon';
import { Warning as WarningIcon } from '@phosphor-icons/react';
import { useAtomValue } from 'jotai';
import { FieldErrors, FormProvider, useForm, useWatch } from 'react-hook-form';

import { ChangeEmailRequestStatus } from '@/api/types/auth/changeEmail';
import EditableEmailField from '@/components/forms/fields/EditableEmailField';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import useUserChangeEmail from '@/hooks/settings/useUserChangeEmail';
import { authUserAtom } from '@/state/auth';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

type FormValues = {
  email: string;
};

export default function UserEditEmailSection() {
  const user = useAtomValue(authUserAtom);

  const [isEditingEmail, setIsEditingEmail] = useState<boolean>(false);

  const formContext = useForm<{
    email: string;
  }>({
    defaultValues: {
      email: user.email,
    },
  });
  const {
    handleSubmit,
    control,
    setFocus,
    setValue,
    reset,
    formState: { isSubmitting },
  } = formContext;

  const currentEmail = useWatch({ control, name: 'email' });

  const { BackendErrorsDisplay, errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>(
    { control },
  );

  const onSuccessfullyChanged = useCallback(
    ({ toEmail }: { toEmail: string }) => {
      setValue('email', toEmail);
      setIsEditingEmail(false);
      reset({ email: toEmail });
    },
    [setValue, reset],
  );

  const { isLoading, isRefreshing, changeEmailRequest, requestChange, refresh } =
    useUserChangeEmail({
      onSuccessfullyChanged,
    });

  const stateComponents = useMemo<['empty' | 'pending', 'empty' | 'matches' | 'different']>(() => {
    const matchState =
      !changeEmailRequest.toEmail || !currentEmail
        ? 'empty'
        : changeEmailRequest.toEmail === currentEmail
          ? 'matches'
          : 'different';

    if (
      [ChangeEmailRequestStatus.PENDING, ChangeEmailRequestStatus.EXPIRED].includes(
        changeEmailRequest.status,
      ) &&
      changeEmailRequest.toEmail
    ) {
      return ['pending', matchState];
    }

    return ['empty', matchState];
  }, [changeEmailRequest.status, changeEmailRequest.toEmail, currentEmail]);

  const emailState = useMemo<'empty' | 'pending'>(() => {
    return stateComponents[0];
  }, [stateComponents]);

  const matchState = useMemo<'empty' | 'matches' | 'different'>(() => {
    return stateComponents[1];
  }, [stateComponents]);

  const actionToTake = useMemo<'none' | 'send' | 'resend'>(() => {
    if (emailState === 'pending' && matchState === 'matches') return 'resend';
    if (!currentEmail || currentEmail === user.email) return 'none';
    return 'send';
  }, [currentEmail, user.email, emailState, matchState]);

  const sendActionText = actionToTake === 'resend' ? 'Resend Verification' : 'Send Verification';

  const onSubmit = useCallback(
    async (data: FormValues) => {
      const request = requestChange({ toEmail: data.email });
      const wrapped = await errorWrappedRequest(request);
      if (!wrapped.hasError) {
        toaster.create({
          title: `${actionToTake === 'resend' ? 'Resent' : 'Sent'} Verification Email`,
          description: `Sent to ${wrapped.result.toEmail}.`,
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });
      }
    },
    [actionToTake, requestChange, errorWrappedRequest],
  );

  const onError = useCallback(
    async (errors: FieldErrors<FormValues>) => {
      scrollToFirstHookFormError({ errors, setFocus });
    },
    [setFocus],
  );

  const onCancel = useCallback(() => {
    setIsEditingEmail(false);
    reset();
  }, [reset]);

  const handleRefreshClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      void refresh();
    },
    [refresh],
  );

  return (
    <FormProvider {...formContext}>
      <chakra.form onSubmit={handleSubmit(onSubmit, onError)} w="100%">
        <VStack gap="2" alignItems="stretch">
          <VStack gap="6" alignItems="stretch">
            <HStack gap="3" columnGap="2" wrap="wrap">
              <EditableEmailField
                name={'email'}
                label={'Email/Username'}
                description="You will need to verify a new email in order to update."
                required
                isEditable={isEditingEmail}
                setIsEditable={setIsEditingEmail}
                labelForEdit="Edit email"
                labelForDoneEditing="Done editing email"
                showDoneEditingIcon={false}
                shouldSetNotEditableOnBlur={false}
              />
              {isEditingEmail && (
                <VStack gap="4" align="flex-start">
                  <HStack gap="1">
                    <Button
                      size="sm"
                      disabled={
                        isLoading || isRefreshing || isSubmitting || actionToTake === 'none'
                      }
                      loading={isSubmitting}
                      type="submit"
                      variant="solid"
                    >
                      {sendActionText}
                    </Button>
                    <Button size="sm" onClick={onCancel} colorPalette="gray" variant="ghost">
                      Cancel
                    </Button>
                  </HStack>
                  {actionToTake === 'resend' && (
                    <HStack>
                      <Button
                        size="sm"
                        onClick={handleRefreshClick}
                        disabled={isLoading || isRefreshing || isSubmitting}
                        loading={isRefreshing && !isLoading}
                      >
                        Refresh Status
                        <Icon>
                          <ArrowPathIcon />
                        </Icon>
                      </Button>
                    </HStack>
                  )}
                </VStack>
              )}
            </HStack>
          </VStack>
          <VStack gap="6">
            <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
          </VStack>
          {isEditingEmail && actionToTake !== 'none' && (
            <VStack gap="6">
              <HStack gap="1">
                <Icon color="warning.bg.main" fontSize="1.25rem">
                  <WarningIcon weight="fill" />
                </Icon>
                <Text textStyle="body2" color="warning.text.main">
                  You are required to verify your new email before it is saved.
                </Text>
              </HStack>
            </VStack>
          )}
        </VStack>
      </chakra.form>
    </FormProvider>
  );
}
