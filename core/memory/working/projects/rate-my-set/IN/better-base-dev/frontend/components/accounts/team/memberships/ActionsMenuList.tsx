import { useCallback } from 'react';

import { useDisclosure } from '@chakra-ui/react';

import { Membership } from '@/api/types/accounts/memberships';
import { MenuContent, MenuContentProps, MenuItem, MenuSeparator } from '@/components/ui/menu';
import { ActionMenuBaseProps } from '@/utils/types/ListItemAction';

import MembershipUpdateRoleDialog from './modals/MembershipUpdateRoleDialog';

type BaseProps = ActionMenuBaseProps<Membership>;
type Props = BaseProps & MenuContentProps;

export default function MembershipActionsMenu({ obj, onAction, ...rest }: Props) {
  return (
    <MenuContent {...rest}>
      <UpdateMembershipRoleMenuItem obj={obj} onAction={onAction} />
      <MenuSeparator w="96%" ml="2%" />
      {/* TODO: Implement 'Remove member' with membershipService. */}
      {/* TODO: Standardize MenuItem styles. */}
      <MenuItem
        color="fg.error"
        value="Remove Member"
        _hover={{
          bg: 'bg.error',
        }}
        _active={{
          bg: 'bg.error',
        }}
        cursor="pointer"
      >
        Remove Member
      </MenuItem>
    </MenuContent>
  );
}

function UpdateMembershipRoleMenuItem({ obj, onAction }: Pick<BaseProps, 'obj' | 'onAction'>) {
  const { open: isOpen, onOpen, onClose } = useDisclosure();

  const onSuccess = useCallback(
    ({ obj: updatedObj }: { obj: Membership }) => {
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
      <MenuItem onClick={onOpen} value="Update Role" cursor="pointer">
        Update Role
      </MenuItem>
      <MembershipUpdateRoleDialog
        open={isOpen}
        onOpenChange={(e) => !e.open && onClose()}
        obj={obj}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    </>
  );
}
