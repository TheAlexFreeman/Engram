import { useCallback, useEffect, useMemo, useState } from 'react';

import { Box, HStack, Icon, IconButton, Text } from '@chakra-ui/react';
import { DotsThree as DotsThreeIcon, User as UserIcon } from '@phosphor-icons/react';
import { createFileRoute, useLoaderData, useRouter } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { AccountType } from '@/api/types/accounts/accounts';
import { Invitation } from '@/api/types/accounts/invitations';
import { Membership, Role } from '@/api/types/accounts/memberships';
import Invitations from '@/components/accounts/team/Invitations';
import InvitationCreateDialog from '@/components/accounts/team/invitations/modals/InvitationCreateDialog';
import MembershipActionsMenu from '@/components/accounts/team/memberships/ActionsMenuList';
import DataList, { ColumnDef } from '@/components/dataDisplay/DataList';
import { Avatar } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { MenuRoot, MenuTrigger } from '@/components/ui/menu';
import { Tag } from '@/components/ui/tag';
import invitationService from '@/services/invitations';
import membershipService from '@/services/memberships';
import { authUserAtom, currentMembershipAtom } from '@/state/auth';
import store from '@/state/store';
import { Action } from '@/utils/types/ListItemAction';

export const Route = createFileRoute('/_auth/accounts/$accountId/team')({
  loader: teamLoader,
  component: Team,
});

async function teamLoader({ params: { accountId } }: { params: { accountId: string } }): Promise<{
  memberships: Membership[];
  invitations: Invitation[];
}> {
  let resolvedAccountId;
  if (accountId == 'current') {
    const m = store.get(currentMembershipAtom);
    resolvedAccountId = m?.account.id;
  } else {
    resolvedAccountId = accountId;
  }

  const [memberships, invitations] = (await Promise.all([
    membershipService.list({ params: { accountId: resolvedAccountId as string } }),
    invitationService.list({
      params: {
        accountId: resolvedAccountId as string,
        isAccepted: false,
        isDeclined: false,
      },
    }),
  ])) as [Membership[], Invitation[]];

  return { memberships, invitations };
}

function Team() {
  const router = useRouter();

  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const closeInviteModal = useCallback(() => setIsInviteModalOpen(false), []);

  const currentMembership = useAtomValue(currentMembershipAtom) as NonNullable<Membership>;

  const { memberships: initialMembershipList, invitations } = Route.useLoaderData();

  const user = useAtomValue(authUserAtom);
  const account = useLoaderData({ from: '/_auth/accounts/$accountId' });
  const [memberships] = useState<Membership[]>(initialMembershipList);

  const [invitationList, setInvitationList] = useState<Invitation[]>(invitations);

  const showInvitations = useMemo(
    () =>
      account.accountType === AccountType.TEAM &&
      currentMembership.role === Role.OWNER &&
      invitationList.length > 0,
    [account.accountType, currentMembership.role, invitationList.length],
  );

  // Adding Invitations -----------------------------------------
  const handleAddNewInvitation = () => {
    setIsInviteModalOpen(true);
  };

  const handleInvitationCreated = useCallback(
    ({ obj }: { obj: Invitation }) => {
      closeInviteModal();
      setInvitationList((v) => [obj, ...v]);

      void router.invalidate();
    },
    [closeInviteModal, router],
  );

  // Membership Operations ---------------------------------------------

  const [rows, setRows] = useState<Membership[]>(memberships);

  const getMemberships = useCallback(() => {
    setRows(memberships);
  }, [memberships]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    getMemberships();
  }, [getMemberships]);

  const handleRoleChange = useCallback(
    ({ action, result, obj }: Action<Membership>) => {
      if (action === 'update' && result === 'success') {
        setRows(rows.map((member) => (member.id === obj.id ? obj : member)));
      }
    },
    [rows],
  );

  const renderNameCell = useCallback(
    (row: Membership) => {
      return (
        <HStack gap="2" p="1.5" maxW="1200px">
          <Avatar
            variant="outline"
            size="sm"
            src={row.user.uploadedProfileImage}
            name={row.user.name || undefined}
            aria-label={row.user.name || undefined}
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
          <Box textStyle="inherit">
            {row.user.name === user.name ? `${row.user.name} (You)` : row.user.name}
          </Box>
        </HStack>
      );
    },
    [user.name],
  );

  const renderRoleCell = useCallback((row: Membership) => {
    const { role, roleDisplay } = row;
    if (role !== Role.OWNER) return roleDisplay;
    return (
      <Tag
        textStyle="buttonM"
        color="primary.text.main"
        bgColor="primary.bg.lighter"
        borderRadius="xl"
      >
        {roleDisplay}
      </Tag>
    );
  }, []);

  const renderActionsCell = useCallback(
    (row: Membership) => {
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
          <MembershipActionsMenu obj={row} onAction={handleRoleChange} />
        </MenuRoot>
      );
    },
    [handleRoleChange],
  );

  const columnDefs = useMemo(() => {
    const result: ColumnDef<Membership>[] = [
      { field: 'user.name', label: 'Team member', renderCell: renderNameCell },
      { field: 'user.email', label: 'Email' },
      { field: 'role', label: 'Role', renderCell: renderRoleCell },
    ];
    if (currentMembership.role === Role.OWNER) {
      result.push({ columnType: 'custom', key: 'actions', renderCell: renderActionsCell });
    }
    return result;
  }, [currentMembership.role, renderActionsCell, renderNameCell, renderRoleCell]);

  return (
    <>
      <HStack direction="row" justifyContent="space-between" mb="4">
        <Text fontSize="2xl">Team</Text>
        {account.accountType === AccountType.TEAM && (
          <>
            <Button onClick={handleAddNewInvitation} variant="outline">
              Invite
            </Button>
            <InvitationCreateDialog
              open={isInviteModalOpen}
              onSuccess={handleInvitationCreated}
              onCancel={() => setIsInviteModalOpen(false)}
              onOpenChange={(e) => !e.open && setIsInviteModalOpen(false)}
              obj={currentMembership}
            />
          </>
        )}
      </HStack>
      <Box mb={8}>
        <DataList columnDefs={columnDefs} rows={rows} />
      </Box>

      {showInvitations && (
        <Invitations invitations={invitationList} handleSetInvitations={setInvitationList} />
      )}
    </>
  );
}
