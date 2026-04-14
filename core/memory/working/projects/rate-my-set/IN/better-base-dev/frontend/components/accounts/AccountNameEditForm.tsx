import { useCallback, useMemo } from 'react';

import { Account } from '@/api/types/accounts/accounts';
import ConnectedSingleEditableFieldForm, {
  type ConnectedSingleEditableFieldFormValues,
} from '@/components/forms/ConnectedSingleEditableFieldForm';
import accountService from '@/services/accounts';

interface Props {
  account: Account;
  onSuccess?: () => void;
}

export default function AccountNameEditForm({ account, onSuccess }: Props) {
  const save = useCallback(
    async ({ name }: { name: string }) => {
      return accountService.update(account.id, { name });
    },
    [account],
  );

  const successToast = useMemo(() => {
    return {
      title: 'Account name updated',
      description: 'Account name has been updated to "$new.name" from "$old.name".',
    };
  }, []);

  return (
    <ConnectedSingleEditableFieldForm
      obj={account}
      fieldName="name"
      fieldLabel="Account Name"
      save={save as (data: ConnectedSingleEditableFieldFormValues) => Promise<Account>}
      successToast={successToast}
      autocomplete="name"
      required={false}
      onSuccess={onSuccess}
    />
  );
}
