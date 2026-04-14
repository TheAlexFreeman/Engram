import { type DialogRootProps, VStack, chakra } from '@chakra-ui/react';
import { useAtomValue } from 'jotai';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import { Invitation } from '@/api/types/accounts/invitations';
import { Membership, Role } from '@/api/types/accounts/memberships';
import InputField from '@/components/forms/fields/InputField';
import { Button } from '@/components/ui/button';
import {
  DialogBackdrop,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
} from '@/components/ui/dialog';
import { toaster } from '@/components/ui/toaster';
import useHookFormBackendErrorsDisplay from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import invitationService from '@/services/invitations';
import { authUserAtom } from '@/state/auth';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

type FormValues = {
  email: string;
  name: string;
  role: Role;
};

type OnSuccessObj = {
  obj: Invitation;
  formValues: FormValues;
};

type Props = {
  obj: Membership;
  onSuccess: (obj: OnSuccessObj) => void;
  onCancel: () => void;
} & Omit<DialogRootProps, 'children'>;

export default function InvitationCreateDialog({ obj, onSuccess, onCancel, ...rest }: Props) {
  const user = useAtomValue(authUserAtom);

  const formContext = useForm<FormValues>({
    defaultValues: {
      email: '',
      name: '',
      role: Role.MEMBER,
    },
  });
  const {
    handleSubmit,
    control,
    setFocus,
    formState: { isSubmitting },
    reset,
  } = formContext;

  const { BackendErrorsDisplay, errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>(
    { control },
  );

  const onSubmit = async (data: FormValues) => {
    const request = invitationService.create({
      ...data,
      accountId: obj.account.id,
      invitedById: user.id,
    });

    const wrapped = await errorWrappedRequest(request);
    if (!wrapped.hasError) {
      toaster.create({
        title: 'Invitation sent',
        description: `1 invitation sent!`,
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });
      onSuccess({ obj: wrapped.result, formValues: data });
      reset();
    }
  };

  const onError = async (errors: FieldErrors<FormValues>) => {
    scrollToFirstHookFormError({ errors, setFocus });
  };

  const handleCancel = () => {
    reset();
    onCancel();
  };

  return (
    <DialogRoot {...rest} onOpenChange={(e) => !e.open && handleCancel()}>
      <DialogBackdrop />
      <DialogContent>
        <DialogHeader>Invite New Member</DialogHeader>
        <DialogCloseTrigger onClick={handleCancel} />
        <DialogBody>
          <FormProvider {...formContext}>
            <chakra.form onSubmit={handleSubmit(onSubmit, onError)} width="100%">
              <VStack gap={4} mb="4" alignItems="stretch">
                <VStack>
                  <InputField name={'name'} label={'Name'} />
                  <InputField
                    name={'email'}
                    label={'Email Address'}
                    placeholder="example@email.com"
                    required
                  />
                </VStack>
              </VStack>
              {/* TODO: Display message if email already exists on pending invitation */}
              {/* (requires backend validation on change) Use Invitation list endpoint */}
              <VStack gap={4}>
                <BackendErrorsDisplay alignSelf="flex-start" maxW="100%" />
              </VStack>
            </chakra.form>
          </FormProvider>
        </DialogBody>
        <DialogFooter justifyContent="space-between">
          <Button onClick={handleCancel} disabled={isSubmitting} variant="ghost">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit(onSubmit, onError)}
            disabled={isSubmitting}
            loading={isSubmitting}
          >
            Send
          </Button>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  );
}
