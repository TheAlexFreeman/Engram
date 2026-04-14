import { useCallback } from 'react';

import { type DialogRootProps, VStack, chakra } from '@chakra-ui/react';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import { Membership, Role, roleChoices } from '@/api/types/accounts/memberships';
import ReactSelectField from '@/components/forms/fields/ReactSelectField';
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
import membershipService from '@/services/memberships';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

interface FormValues {
  role: { value: Role; label: string };
}

type OnSuccessObj = {
  obj: Membership;
  formValues: FormValues;
};

type Props = {
  obj: Membership;
  onSuccess: (obj: OnSuccessObj) => void;
  onCancel: () => void;
} & Omit<DialogRootProps, 'children'>;

export default function MembershipUpdateRoleDialog({ obj, onSuccess, onCancel, ...rest }: Props) {
  const formContext = useForm<FormValues>({
    defaultValues: {
      role: { value: obj.role, label: obj.roleDisplay },
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

  const onSubmit = useCallback(
    async (data: FormValues) => {
      const request = membershipService.updateRole(obj.id, data.role.value);
      const wrapped = await errorWrappedRequest(request);
      if (!wrapped.hasError) {
        toaster.create({
          title: 'Updated role',
          description: `Successfully updated role for ${obj.user.email}.`,
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });
        onSuccess({ obj: wrapped.result, formValues: data });
        reset();
      }
    },
    [errorWrappedRequest, obj.id, obj.user.email, onSuccess, reset],
  );

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
        <DialogHeader>Update Role</DialogHeader>
        <DialogCloseTrigger onClick={handleCancel} />
        <DialogBody>
          <FormProvider {...formContext}>
            <chakra.form onSubmit={handleSubmit(onSubmit, onError)} width="100%">
              <VStack gap={4} mb="4" alignItems="stretch">
                <ReactSelectField
                  required
                  name="role"
                  label="Role"
                  placeholder="Select Role"
                  slotProps={{
                    select: {
                      options: roleChoices,
                      isClearable: false,
                    },
                  }}
                />
              </VStack>
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
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  );
}
