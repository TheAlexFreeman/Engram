import { useCallback, useMemo } from 'react';

import { useAtomValue } from 'jotai';

import { User } from '@/api/types/accounts/users';
import ConnectedSingleEditableFieldForm, {
  type ConnectedSingleEditableFieldFormValues,
} from '@/components/forms/ConnectedSingleEditableFieldForm';
import userService from '@/services/users';
import { authUserAtom } from '@/state/auth';

export default function UserEditNameSection() {
  const user = useAtomValue(authUserAtom);

  const save = useCallback(
    ({ name }: { name: string }) => {
      return userService.update(user.id, { name });
    },
    [user.id],
  );

  const successToast = useMemo(() => {
    return {
      title: 'Name updated',
      description: 'Your name has been updated to "$new.name" from "$old.name".',
    };
  }, []);

  return (
    <ConnectedSingleEditableFieldForm
      obj={user}
      fieldName="name"
      fieldLabel="Name"
      save={save as (data: ConnectedSingleEditableFieldFormValues) => Promise<User>}
      successToast={successToast}
      autocomplete="name"
      required={false}
    />
  );
}
