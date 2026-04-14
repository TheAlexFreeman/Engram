import { useCallback, useMemo, useState } from 'react';

import { Badge, Box, HStack, Icon, Spacer, Text, VStack } from '@chakra-ui/react';
import {
  CaretRight,
  CheckCircle,
  UsersFour as TeamIcon,
  User as UserIcon,
} from '@phosphor-icons/react';
import { useAtomValue } from 'jotai';

import { Account } from '@/api/types/accounts/accounts';
import { Membership, Role } from '@/api/types/accounts/memberships';
import { CheckUserDeleteResult, User } from '@/api/types/accounts/users';
import { SingleSelectableDataList } from '@/components/dataDisplay/SelectableDataList';
import { Avatar } from '@/components/ui/avatar';
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
import { Tag } from '@/components/ui/tag';
import membershipService from '@/services/memberships';
import { membershipsAtom } from '@/state/auth';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  onNext: () => void;
  checkResult: CheckUserDeleteResult | null;
}

interface TransferOwnershipBoxProps {
  membership: Membership;
  handleTransferClick: (membership: Membership) => void;
  isTransferred: boolean;
}

interface AccountsToTransferProps {
  memberships: Membership[];
  onSelect: (a: Account) => void;
  transferredAccounts: Account[];
}

interface TransferAccountProps {
  account: Account;
  memberships: Membership[];
  user: User;
  selectedMember?: Membership;
  onMemberSelected: (m: Membership) => void;
}

export default function TransferOwnershipModal({ open, onClose, onNext, checkResult }: ModalProps) {
  const manualActions = checkResult?.manualActionsOffered;
  const memberships = useAtomValue(membershipsAtom);
  const user = checkResult?.user || memberships[0].user;

  const transferMemberships = useMemo(() => {
    if (manualActions === undefined) return [];
    const membershipsToTransfer = [];

    for (const membership of memberships) {
      const id = membership.account.id;

      if (manualActions[id] && manualActions[id]['other-members']) {
        membershipsToTransfer.push(membership);
      }
    }

    return membershipsToTransfer;
  }, [manualActions, memberships]);

  const [transferringAccount, setTransferringAccount] = useState<Account | null>(null);
  const [transferredAccounts, setTransferredAccounts] = useState<Account[]>([]);
  const [teamMembers, setTeamMembers] = useState<Membership[]>([]);
  const handleAccountSelected = async (account: Account) => {
    setTransferringAccount(account);
    const accountMemberships = await membershipService.list({ params: { accountId: account.id } });
    setTeamMembers(accountMemberships as Membership[]);
  };

  const [selectedMember, setSelectedMember] = useState<Membership | undefined>(undefined);
  const handleMemberSelected = useCallback(
    (m: Membership) => setSelectedMember(selectedMember === m ? undefined : m),
    [selectedMember],
  );

  const saveTransfer = useCallback(async () => {
    if (selectedMember && transferringAccount) {
      await membershipService.updateRole(selectedMember.id, Role.OWNER);
      setTransferredAccounts([...transferredAccounts, transferringAccount]);
      setTransferringAccount(null);
    }
  }, [selectedMember, transferredAccounts, transferringAccount]);

  const { backButtonAction, backButtonText, nextButtonAction, nextButtonText, nextButtonDisabled } =
    useMemo(
      () =>
        transferringAccount === null
          ? {
              backButtonText: 'Cancel',
              backButtonAction: onClose,
              nextButtonText: 'Next',
              nextButtonAction: onNext,
              nextButtonDisabled: transferMemberships.some(
                (m) => !transferredAccounts.includes(m.account),
              ),
            }
          : {
              backButtonText: 'Back',
              backButtonAction: () => {
                setSelectedMember(undefined);
                setTransferringAccount(null);
              },
              nextButtonText: 'Save',
              nextButtonAction: saveTransfer,
              nextButtonDisabled: selectedMember === undefined,
            },
      [
        onClose,
        onNext,
        saveTransfer,
        selectedMember,
        transferMemberships,
        transferredAccounts,
        transferringAccount,
      ],
    );

  return (
    <DialogRoot open={open} onOpenChange={(e) => !e.open && onClose()} size="xl">
      <DialogBackdrop />
      <DialogContent>
        <DialogHeader>
          <Text textStyle="h4">Transfer Ownership required</Text>
        </DialogHeader>
        <DialogCloseTrigger onClick={onClose} />
        {transferringAccount === null ? (
          <AccountsToTransfer
            memberships={transferMemberships}
            transferredAccounts={transferredAccounts}
            onSelect={handleAccountSelected}
          />
        ) : (
          <TransferAccount
            account={transferringAccount}
            memberships={teamMembers}
            user={user}
            selectedMember={selectedMember}
            onMemberSelected={handleMemberSelected}
          />
        )}
        <DialogFooter justifyContent="space-between">
          <Button
            size="md"
            variant={'outline'}
            borderColor={'bg.level3'}
            borderWidth={2}
            color="text.main"
            onClick={backButtonAction}
          >
            {backButtonText}
          </Button>
          <Button
            size="md"
            variant={'solid'}
            colorPalette="red"
            disabled={nextButtonDisabled}
            onClick={nextButtonAction}
          >
            {nextButtonText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  );
}

function TransferAccount({
  account,
  memberships,
  user,
  selectedMember,
  onMemberSelected,
}: TransferAccountProps) {
  const { displayName, uploadedProfileImage } = account;

  const renderNameCell = useCallback(
    (row: Membership) => {
      const { email, name, uploadedProfileImage: memberUploadedProfileImage } = row.user;
      return (
        <HStack gap="2">
          <Avatar
            variant="outline"
            size="sm"
            src={memberUploadedProfileImage}
            name={name || undefined}
            aria-label={name || undefined}
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
          <Box textStyle="inherit">{email === user.email ? `${name} (You)` : name}</Box>
        </HStack>
      );
    },
    [user],
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

  return (
    <DialogBody>
      <HStack
        backgroundColor="bg.level1"
        borderRadius={'md'}
        px={3}
        py={2}
        mb={3}
        width="fit-content"
      >
        <Avatar
          variant="outline"
          size="sm"
          src={uploadedProfileImage}
          name={displayName}
          borderColor="primary.text.light"
          borderWidth="2px"
          bg="transparent"
          color="primary.text.main"
        />
        <Text textStyle={'h4'}>{displayName}</Text>
      </HStack>
      <Text textStyle="body1">
        Please indicate one member to take over ownership for this account.
      </Text>

      <SingleSelectableDataList
        columnDefs={[
          { field: 'user.name', label: 'Team member', renderCell: renderNameCell },
          { field: 'user.email', label: 'Email' },
          { field: 'role', label: 'Role', renderCell: renderRoleCell },
        ]}
        rows={memberships}
        onRowSelected={onMemberSelected}
        selectedRow={selectedMember}
        exclude={(m: Membership) => m.user.id === user.id}
      />
    </DialogBody>
  );
}

function AccountsToTransfer({
  memberships,
  onSelect,
  transferredAccounts,
}: AccountsToTransferProps) {
  return (
    <DialogBody>
      <VStack gap={6}>
        <Text textStyle={'body1'}>
          Deleting everything will delete all your data belonging to your personal account and
          remove your membership from all team accounts.
        </Text>
        <Text textStyle={'body1'}>
          You are currently the only owner in the following account
          {memberships.length === 1 ? '' : 's'}. Please transfer your ownership to another user
          before deleting everything.
        </Text>
        {memberships.map((membership) => (
          <TransferOwnershipBox
            key={membership.id}
            membership={membership}
            isTransferred={transferredAccounts.includes(membership.account)}
            handleTransferClick={(m) => onSelect(m.account)}
          />
        ))}
      </VStack>
    </DialogBody>
  );
}

function TransferOwnershipBox({
  membership,
  handleTransferClick,
  isTransferred,
}: TransferOwnershipBoxProps) {
  const { displayName, uploadedProfileImage } = membership.account;

  return (
    <Box borderRadius="md" border="1px" width="100%" p={4}>
      <HStack justifyContent={'space-between'}>
        <Avatar
          variant="outline"
          size="sm"
          src={uploadedProfileImage}
          name={displayName}
          borderColor="primary.text.light"
          borderWidth="2px"
          bg="transparent"
          color="primary.text.main"
        />
        <VStack gap={0} alignItems="flex-start">
          <Text textStyle="h4">{displayName} </Text>
          <HStack>
            <Text textStyle="body2" color="text.lighter">
              <Icon asChild>
                <TeamIcon weight="fill" fontSize="1em" />
              </Icon>
              Team Account
            </Text>
            {membership.role === Role.OWNER && (
              <Badge color="purple.500" p={1} borderRadius="xl" fontSize="8px" textTransform="none">
                Owner
              </Badge>
            )}
          </HStack>
        </VStack>
        <Spacer />
        {isTransferred ? (
          <Text color="success.text.light" textStyle="buttonL" fontWeight="semibold" mr={6}>
            <Icon asChild pos="relative" top={0.5} mr={2}>
              <CheckCircle weight="bold"></CheckCircle>
            </Icon>
            Transfer Complete
          </Text>
        ) : (
          <Button
            variant="ghost"
            mr={0}
            size={'md'}
            onClick={() => handleTransferClick(membership)}
          >
            Transfer Ownership
            <CaretRight weight="fill" />
          </Button>
        )}
      </HStack>
    </Box>
  );
}
