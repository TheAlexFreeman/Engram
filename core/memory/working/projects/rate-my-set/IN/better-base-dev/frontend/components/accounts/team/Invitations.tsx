import { useCallback, useEffect, useState } from 'react';

import { Box, HStack, Icon, IconButton, Text } from '@chakra-ui/react';
import { DotsThree as DotsThreeIcon, User as UserIcon } from '@phosphor-icons/react';

import { Invitation } from '@/api/types/accounts/invitations';
import DataList from '@/components/dataDisplay/DataList';
import { Avatar } from '@/components/ui/avatar';
import { MenuRoot, MenuTrigger } from '@/components/ui/menu';
import { Action } from '@/utils/types/ListItemAction';

import InvitationActionsMenu from './invitations/ActionsMenuList';

interface Props {
  invitations: Invitation[];
  handleSetInvitations: (
    invitations: Invitation[] | ((prevInvitations: Invitation[]) => Invitation[]),
  ) => void;
}

function Invitations({ invitations }: Props) {
  const [rows, setRows] = useState<Invitation[]>([]);

  useEffect(() => {
    setRows(invitations);
  }, [invitations]);

  const renderNameCell = useCallback((row: Invitation) => {
    return (
      <HStack gap="2" p="1.5" maxW="1200px">
        <Avatar
          variant="outline"
          size="sm"
          name={row.name || undefined}
          src={row.user?.uploadedProfileImage}
          aria-label={row.name || undefined}
          color="primary.text.main"
          bgColor="transparent"
          borderColor="primary.bg.main"
          borderWidth="2px"
          icon={
            <Icon color="primary.text.light">
              <UserIcon weight="fill" fontSize="1rem" />
            </Icon>
          }
        />
        <Box textStyle="inherit">{row.name}</Box>
      </HStack>
    );
  }, []);

  const renderRoleCell = useCallback((row: Invitation) => {
    if (row.isExpired) {
      return <Text color="fg.error">Expired</Text>;
    } else {
      return <Text color="primary.text.lighter">Pending</Text>;
    }
  }, []);

  const handleInvitationAction = useCallback(({ action, result, obj }: Action<Invitation>) => {
    if (action === 'delete' && result === 'success') {
      setRows((prevInvitations) => prevInvitations.filter((i) => i.id !== obj.id));
    } else if (action === 'update' && result === 'success') {
      setRows((prevInvitations) => prevInvitations.map((i) => (i.id === obj.id ? obj : i)));
    }
  }, []);

  const renderActionsCell = useCallback(
    (row: Invitation) => {
      return (
        <MenuRoot>
          <MenuTrigger asChild>
            <IconButton
              variant="ghost"
              _active={{
                bgColor: 'bg.level1',
              }}
              _hover={{
                bgColor: 'bg.level1',
              }}
            >
              <Icon color="text.main" fontSize="2rem">
                <DotsThreeIcon />
              </Icon>
            </IconButton>
          </MenuTrigger>
          <InvitationActionsMenu obj={row} onAction={handleInvitationAction} />
        </MenuRoot>
      );
    },
    [handleInvitationAction],
  );

  return (
    <>
      <Text textStyle="h5">Pending invitations</Text>
      <DataList
        columnDefs={[
          { field: 'user.name', label: 'Team member', renderCell: renderNameCell },
          { field: 'email', label: 'Email' },
          { field: 'role', label: 'Role', renderCell: renderRoleCell },
          { columnType: 'custom', key: 'actions', renderCell: renderActionsCell },
        ]}
        rows={rows}
      />
    </>
  );
}

export default Invitations;
