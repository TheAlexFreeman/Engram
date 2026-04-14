import { useCallback } from 'react';

import { useDisclosure } from '@chakra-ui/react';
import { useAtomValue } from 'jotai';

import { Invitation, InvitationStatus } from '@/api/types/accounts/invitations';
import { Role } from '@/api/types/accounts/memberships';
import {
  MenuContent,
  MenuContentProps,
  MenuItem,
  MenuItemGroup,
  MenuSeparator,
} from '@/components/ui/menu';
import { toaster } from '@/components/ui/toaster';
import {
  ErrorWrappedRequestResult,
  wrapRequestWithErrorHandling,
} from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import invitationService from '@/services/invitations';
import { currentMembershipAtom } from '@/state/auth';
import { getBestSingleErrorMessageFor } from '@/utils/errors';
import { ActionMenuBaseProps } from '@/utils/types/ListItemAction';

import InvitationUpdateDialog from './modals/InvitationUpdateDialog';

type BaseProps = ActionMenuBaseProps<Invitation>;
type Props = BaseProps & MenuContentProps;

export default function InvitationActionsMenu({ obj, onAction, ...rest }: Props) {
  const currentMembership = useAtomValue(currentMembershipAtom);
  const canEditInvitation =
    currentMembership?.role === Role.OWNER && obj.status === InvitationStatus.OPEN;

  const date = new Date(obj.lastSentAt as string);
  const displayDate = date.toLocaleDateString();
  const displayTime = date.toLocaleTimeString([], { timeStyle: 'short' });

  return (
    <MenuContent {...rest}>
      <MenuItemGroup
        fontSize="xs"
        color="primary.text.lighter"
        title={`Invitation sent ${displayDate} at ${displayTime} `}
      >
        <MenuSeparator />

        <ResendInvitationItem obj={obj} onAction={onAction} />
        <RemoveInvitationItem obj={obj} onAction={onAction} />
        {canEditInvitation && <EditInvitationItem obj={obj} onAction={onAction} />}
      </MenuItemGroup>
    </MenuContent>
  );
}

function ResendInvitationItem({ obj }: Pick<BaseProps, 'obj' | 'onAction'>) {
  const handleClick = async () => {
    await invitationService.resend(obj.id);
    toaster.create({
      title: 'Invitation Resent',
      description: `Resent invitation to ${obj.email}`,
      type: 'success',
      duration: 7000,
      meta: { closable: true },
    });
  };

  return (
    <MenuItem onClick={handleClick} value="Resend Invitation" cursor="pointer">
      Resend Invitation
    </MenuItem>
  );
}

function RemoveInvitationItem({ obj, onAction }: Pick<BaseProps, 'obj' | 'onAction'>) {
  const handleClick = async () => {
    let wrapped: ErrorWrappedRequestResult<void> | null = null;
    try {
      const request = invitationService.delete(obj.id);

      wrapped = await wrapRequestWithErrorHandling({ awaitable: request });

      if (wrapped.hasError) {
        const errorMessage = getBestSingleErrorMessageFor(wrapped.error);

        toaster.create({
          title: 'Failed to Delete Invitation',
          description: errorMessage,
          type: 'error',
          duration: 10000,
          meta: { closable: true },
        });
        if (onAction != null) {
          onAction({ action: 'delete', result: 'failure', obj });
        }
      }
    } finally {
      if (wrapped && !wrapped.hasError) {
        toaster.create({
          title: 'Invitation Removed',
          description: `Removed invitation for ${obj.email}`,
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });
        if (onAction != null) {
          onAction({ action: 'delete', result: 'success', obj });
        }
      }
    }
  };

  return (
    <MenuItem onClick={handleClick} value="Remove Invitation" cursor="pointer">
      Remove Invitation
    </MenuItem>
  );
}

function EditInvitationItem({ obj, onAction }: Pick<BaseProps, 'obj' | 'onAction'>) {
  const { open: isOpen, onOpen, onClose } = useDisclosure();

  const onSuccess = useCallback(
    ({ obj: updatedObj }: { obj: Invitation }) => {
      onClose();

      if (onAction == null) return;
      onAction({ action: 'update', result: 'success', obj: updatedObj });
    },
    [onAction, onClose],
  );

  const onCancel = useCallback(() => {
    if (onAction != null) {
      onAction({ action: 'update', result: 'cancel', obj });
    }
    onClose();
  }, [onAction, obj, onClose]);

  return (
    <>
      <MenuItem onClick={onOpen} value="Edit Invitation" cursor="pointer">
        Edit Invitation
      </MenuItem>
      <InvitationUpdateDialog
        open={isOpen}
        onOpenChange={(e) => !e.open && onClose()}
        obj={obj}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    </>
  );
}
