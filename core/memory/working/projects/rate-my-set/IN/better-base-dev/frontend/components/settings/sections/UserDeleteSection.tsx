import { ReactElement, useCallback, useState } from 'react';

import { Box, HStack, Icon, List, Text, VStack, useDisclosure } from '@chakra-ui/react';
import UserMinusIcon from '@heroicons/react/24/solid/UserMinusIcon';
import { useNavigate } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { AccountType } from '@/api/types/accounts/accounts';
import { Membership } from '@/api/types/accounts/memberships';
import {
  AutomatedActionsType,
  CheckUserDeleteResult,
  ManualActionsType,
} from '@/api/types/accounts/users';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DialogBackdrop,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
} from '@/components/ui/dialog';
import userService from '@/services/users';
import { authUserAtom, membershipsAtom } from '@/state/auth';

import TransferOwnershipModal from '../modals/TransferOwnershipModal';

export default function UserDeleteSection() {
  const navigate = useNavigate();

  const user = useAtomValue(authUserAtom);
  const memberships = useAtomValue(membershipsAtom);

  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isConfirmChecked, setIsConfirmChecked] = useState(false);
  const [isCannotDeleteModalOpen, setIsCannotDeleteModalOpen] = useState(false);

  const [checkResult, setCheckResult] = useState<CheckUserDeleteResult | null>(null);

  const handleDeleteClick = async () => {
    const deleteCheckResult = await userService.checkDelete(user.id);
    setCheckResult(deleteCheckResult);

    const hasTransferOwnerAction = Object.values(deleteCheckResult.manualActionsOffered).some(
      (actionsByType) =>
        Object.values(actionsByType).some((actions) => actions.includes('transfer-ownership')),
    );

    if (hasTransferOwnerAction) {
      onTransferModalOpen();
    } else if (deleteCheckResult.canDeleteUser) {
      setIsConfirmModalOpen(true);
    } else {
      setIsCannotDeleteModalOpen(true);
    }
  };

  const renderManualActions = useCallback(
    (membership: Membership, manualActions: ManualActionsType | null) => {
      const { id, displayName } = membership.account;

      if (!manualActions || !manualActions[id]) {
        return <div key={id}></div>;
      }

      const actions = manualActions[id];
      const actionsArray: ReactElement[] = [];
      actionsArray.push(
        <Text key={id} textStyle="h4">
          {displayName}{' '}
          {actions['other-owners']
            ? '(contains other owners)'
            : actions['other-members']
              ? '(contains other members)'
              : ''}
        </Text>,
      );

      if (actions['other-owners']) {
        const actionsToTake = actions['other-owners'];
        if (actionsToTake.includes('notify-other-owners')) {
          actionsArray.push(
            <List.Item key={id + 'notify'} ml={4}>
              Notify the other owners
            </List.Item>,
          );
        }
        if (actionsToTake.includes('transfer-ownership')) {
          actionsArray.push(
            <List.Item key={id + 'transfer'} ml={4}>
              Tranfer ownership to another member
            </List.Item>,
          );
        }
        if (actionsToTake.includes('delete-account')) {
          actionsArray.push(
            <List.Item key={id + 'delete'} ml={4}>
              Delete the account manually if desired
            </List.Item>,
          );
        }
      }
      if (actions['other-members']) {
        const actionsToTake = actions['other-members'];
        if (actionsToTake.includes('notify-other-owners')) {
          actionsArray.push(
            <List.Item key={id + 'notify'} ml={4}>
              Notify the other owners
            </List.Item>,
          );
        }
        if (actionsToTake.includes('transfer-ownership')) {
          actionsArray.push(
            <List.Item key={id + 'transfer'} ml={4}>
              Tranfer ownership to another member
            </List.Item>,
          );
        }
        if (actionsToTake.includes('delete-account')) {
          actionsArray.push(
            <List.Item key={id + 'delete'} ml={4}>
              Delete the account manually if desired
            </List.Item>,
          );
        }
      }
      return actionsArray;
    },
    [],
  );

  const renderManualActionsRequired = useCallback(
    (membership: Membership) => {
      return renderManualActions(membership, checkResult?.manualActionsRequired || null);
    },
    [checkResult?.manualActionsRequired, renderManualActions],
  );

  const renderManualActionsOffered = useCallback(
    (membership: Membership) => {
      return renderManualActions(membership, checkResult?.manualActionsOffered || null);
    },
    [checkResult?.manualActionsOffered, renderManualActions],
  );

  const renderAutomatedActions = useCallback(
    (membership: Membership) => {
      const { account, id } = membership;
      const automatedActionsPlanned: AutomatedActionsType | null =
        checkResult?.automatedActionsPlanned || null;

      if (!automatedActionsPlanned || !checkResult) {
        return <></>;
      }

      const action = checkResult.automatedActionsPlanned[account.id];

      return (
        <Box mb={1}>
          <HStack alignItems="flex-start">
            <Icon as={UserMinusIcon} boxSize="1.25rem" />
            <VStack alignItems="flex-start" gap={0}>
              <Text key={id} textStyle="h4">
                {account.displayName}
                {account.accountType === AccountType.PERSONAL &&
                  account.displayName !== 'Personal Account' &&
                  '- (Personal Account)'}
              </Text>
              {action === 'delete-account' && (
                <Text textStyle="body1" key={id + 'delete-account'}>
                  Your account and data will be deleted.
                </Text>
              )}
              {action === 'delete-membership' && (
                <Text textStyle="body1" key={id + 'delete-membership'}>
                  Your membership will be removed.
                </Text>
              )}
            </VStack>
          </HStack>
        </Box>
      );
    },
    [checkResult],
  );

  const handleCancel = () => {
    setIsConfirmModalOpen(false);
    setIsCannotDeleteModalOpen(false);
    setIsConfirmChecked(false);
  };

  const handleConfirm = async () => {
    setIsConfirmModalOpen(false);

    await userService.delete(user.id);

    void navigate({ to: '/auth/login', viewTransition: true });
  };
  const {
    open: isTransferModalOpen,
    onOpen: onTransferModalOpen,
    onClose: onTransferModalClose,
  } = useDisclosure();

  const onTransferModalNext = () => {
    onTransferModalClose();
    setIsConfirmModalOpen(true);
  };

  return (
    <>
      <VStack alignItems="flex-start" gap={4}>
        <Text textStyle="h3">Delete everything</Text>
        <TransferOwnershipModal
          open={isTransferModalOpen}
          onClose={onTransferModalClose}
          onNext={onTransferModalNext}
          checkResult={checkResult}
        />
        <Text textStyle="body2" width="sm">
          “Delete everything” will delete all data belonging to you on this platform and all
          personal accounts. Reach out to support anytime to learn more.
        </Text>
        <Button variant="ghost" colorPalette="red" size="sm" onClick={handleDeleteClick}>
          Delete everything
        </Button>
      </VStack>

      {/* Action Required Modal*/}
      <DialogRoot open={isCannotDeleteModalOpen} onOpenChange={(e) => !e.open && handleCancel()}>
        <DialogBackdrop />
        <DialogContent>
          <DialogHeader>Action required before deleting user</DialogHeader>
          <DialogCloseTrigger onClick={handleCancel} />
          <DialogBody>
            <Text mb={2} textStyle="h3">
              Before you can delete this user, you must do the following:
            </Text>
            <Box mb={3}>
              <List.Root>
                {checkResult?.manualActionsRequired &&
                  memberships.map((membership) => (
                    <div key={membership.id}>{renderManualActionsRequired(membership)}</div>
                  ))}
              </List.Root>
            </Box>
          </DialogBody>
          <DialogFooter justifyContent="space-between">
            <Button
              size="md"
              variant={'outline'}
              borderColor={'bg.level3'}
              borderWidth={2}
              color={'text.main'}
              onClick={handleCancel}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </DialogRoot>

      {/* Confirm Modal*/}
      <DialogRoot
        open={isConfirmModalOpen}
        onOpenChange={(e) => !e.open && handleCancel()}
        size="lg"
      >
        <DialogBackdrop />
        <DialogContent>
          <DialogHeader>Are you sure?</DialogHeader>
          <DialogCloseTrigger onClick={handleCancel} />
          <DialogBody>
            <VStack gap={6} alignItems="flex-start">
              <Text textStyle="body1">
                Deleting everything will delete all your data belonging to your personal account and
                remove your membership from all team accounts.
              </Text>
              {checkResult?.shouldOfferManualActionsBeforeDeleting && (
                <Text mb={2} textStyle="h3">
                  Before you delete this user, please manually take care of the following:
                </Text>
              )}
              {checkResult?.manualActionsOffered &&
                Object.keys(checkResult?.manualActionsOffered).length > 0 && (
                  <Box mb={3}>
                    <List.Root>
                      {memberships.map((membership) => (
                        <div key={membership.id}>{renderManualActionsOffered(membership)}</div>
                      ))}
                    </List.Root>
                  </Box>
                )}

              <Box width="100%">
                {checkResult?.automatedActionsPlanned && (
                  <Text mb={6} textStyle="body1">
                    The following actions will automatically occur:
                  </Text>
                )}
                <Box backgroundColor="bg.level1" p={2} borderRadius="md">
                  {memberships.map((membership) => (
                    <VStack alignItems="flex-start" key={membership.id} m={1}>
                      {renderAutomatedActions(membership)}
                    </VStack>
                  ))}
                </Box>
              </Box>

              <Checkbox
                checked={isConfirmChecked}
                onCheckedChange={(e) => setIsConfirmChecked(!!e.checked)}
              >
                <Text textStyle="h4">
                  I understand that pressing delete will remove my account permanently.
                </Text>
              </Checkbox>
            </VStack>
          </DialogBody>
          <DialogFooter justifyContent="space-between">
            <Button
              size="md"
              variant={'outline'}
              borderColor={'bg.level3'}
              borderWidth={2}
              color={'text.main'}
              onClick={handleCancel}
            >
              Cancel
            </Button>
            <Button
              size={'md'}
              onClick={handleConfirm}
              disabled={!isConfirmChecked}
              backgroundColor="danger.bg.contrast"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </DialogRoot>
    </>
  );
}
