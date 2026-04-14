import { useMemo, useState } from 'react';

import { Box, HStack, Icon, IconButton, Spacer, Text, VStack } from '@chakra-ui/react';
import { Trash as TrashIcon, UploadSimple as UploadIcon } from '@phosphor-icons/react';
import { createFileRoute, useLoaderData, useRouter } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { Account, AccountType } from '@/api/types/accounts/accounts';
import { Membership, Role } from '@/api/types/accounts/memberships';
import AccountNameEditForm from '@/components/accounts/AccountNameEditForm';
import UploadImageModal from '@/components/settings/sections/UploadImageModal';
import { Avatar } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import {
  ErrorWrappedRequestResult,
  wrapRequestWithErrorHandling,
} from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import accountService from '@/services/accounts';
import { currentMembershipAtom } from '@/state/auth';
import { getBestSingleErrorMessageFor } from '@/utils/errors';

export const Route = createFileRoute('/_auth/accounts/$accountId/settings')({
  component: AccountSettings,
});

function AccountSettings() {
  const router = useRouter();

  const currentMembership = useAtomValue(currentMembershipAtom) as NonNullable<Membership>;
  let account = useLoaderData({ from: '/_auth/accounts/$accountId' });
  if (account?.id != null && currentMembership.account?.id === account.id) {
    account = currentMembership.account;
  }

  const [isModalOpen, setIsModalOpen] = useState(false);

  const profilePicName = useMemo(() => {
    if (!account.uploadedProfileImage || account.uploadedProfileImage === '') return '';
    const parts = account.uploadedProfileImage.split('--');
    return parts[parts.length - 1];
  }, [account.uploadedProfileImage]);

  const handleUploadSubmit = async (file: File) => {
    const result = await accountService.updateUploadedProfileImage(account.id, file);
    void router.invalidate();
    return result;
  };

  const handleNameChange = () => {
    void router.invalidate();
  };

  const handleDeleteProfilePic = async () => {
    let wrapped: ErrorWrappedRequestResult<Account> | null = null;

    const request = accountService.deleteUploadedProfileImage(account.id);

    wrapped = await wrapRequestWithErrorHandling({ awaitable: request });

    if (wrapped.hasError) {
      const errorMessage = getBestSingleErrorMessageFor(wrapped.error);

      toaster.create({
        title: 'Failed to Delete Picture',
        description: errorMessage,
        type: 'error',
        duration: 10000,
        meta: { closable: true },
      });
    }

    void router.invalidate();
  };

  return (
    <VStack alignItems="flex-start" maxW="400px">
      <Text fontSize="3xl"> Settings</Text>
      <Box mb={5} display="flex" alignItems="center" w="100%">
        <Avatar
          variant="outline"
          size="lg"
          src={account.uploadedProfileImage}
          name={account.name.charAt(0).toUpperCase()}
          color="primary.text.main"
          bgColor="transparent"
          borderColor="primary.bg.main"
          borderWidth="2px"
          mr={4}
          cursor={currentMembership.role === Role.OWNER ? 'pointer' : 'default'}
          _hover={currentMembership.role === Role.OWNER ? { opacity: 0.8 } : undefined}
          onClick={() => {
            if (currentMembership.role === Role.OWNER) {
              setIsModalOpen(true);
            }
          }}
        />
        <VStack alignItems="flex-start" flex={1} minW={0}>
          <Text textStyle="h5">Account Image</Text>
          {account.uploadedProfileImage === null ? (
            <Button
              size="sm"
              onClick={() => setIsModalOpen(true)}
              disabled={currentMembership.role !== Role.OWNER}
            >
              <Icon>
                <UploadIcon />
              </Icon>
              Upload image
            </Button>
          ) : (
            <HStack
              borderRadius="md"
              width="100%"
              px="2"
              backgroundColor="bg.level1"
              cursor={currentMembership.role === Role.OWNER ? 'pointer' : 'default'}
              _hover={
                currentMembership.role === Role.OWNER ? { backgroundColor: 'bg.level2' } : undefined
              }
              onClick={() => {
                if (currentMembership.role === Role.OWNER) {
                  setIsModalOpen(true);
                }
              }}
            >
              <Text lineClamp={1}>{profilePicName}</Text>
              <Spacer />
              <IconButton
                className="delete-button"
                color="text.lighter"
                backgroundColor="transparent"
                aria-label="Remove profile image"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleDeleteProfilePic();
                }}
                disabled={currentMembership.role !== Role.OWNER}
                _hover={{ cursor: 'pointer', color: 'primary.text.main' }}
              >
                <TrashIcon weight="fill" />
              </IconButton>
            </HStack>
          )}
        </VStack>
        <UploadImageModal
          open={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onCancel={() => setIsModalOpen(false)}
          onUploadSubmit={handleUploadSubmit}
        />
      </Box>

      <AccountNameEditForm account={account} onSuccess={handleNameChange} />
      <VStack width={'full'} align="stretch">
        <Text textStyle="h5">Account type</Text>
        <Box backgroundColor="bg.level1" px={3} py={2} borderRadius="md" width="full">
          <Text textStyle="h4">
            {account.accountType === AccountType.PERSONAL ? 'Personal Account' : 'Team Account'}
          </Text>
        </Box>
      </VStack>
    </VStack>
  );
}
