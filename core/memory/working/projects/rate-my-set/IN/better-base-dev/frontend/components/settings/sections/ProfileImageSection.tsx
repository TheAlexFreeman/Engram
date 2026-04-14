import { useMemo, useState } from 'react';

import { Box, HStack, Icon, IconButton, Spacer, Text, VStack } from '@chakra-ui/react';
import {
  Trash as TrashIcon,
  UploadSimple as UploadIcon,
  User as UserIcon,
} from '@phosphor-icons/react';
import { useRouter } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { User } from '@/api/types/accounts/users';
import { Avatar } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import {
  ErrorWrappedRequestResult,
  wrapRequestWithErrorHandling,
} from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import userService from '@/services/users';
import { authUserAtom } from '@/state/auth';
import { textStyles } from '@/theme/text-styles';
import { getBestSingleErrorMessageFor } from '@/utils/errors';

import UploadImageModal from './UploadImageModal';

export default function ProfileImageSection() {
  const router = useRouter();

  const [isModalOpen, setIsModalOpen] = useState(false);

  const user = useAtomValue(authUserAtom);

  const profilePicName = useMemo(() => {
    if (!user.uploadedProfileImage || user.uploadedProfileImage === '') return '';

    const parts = user.uploadedProfileImage.split('--');
    return parts[parts.length - 1];
  }, [user.uploadedProfileImage]);

  const handleDeleteProfilePic = async () => {
    let wrapped: ErrorWrappedRequestResult<User> | null = null;

    const request = userService.deleteUploadedProfileImage(user.id);

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
  };

  const handleUploadSubmit = async (file: File) => {
    const result = await userService.updateUploadedProfileImage(user.id, file);
    void router.invalidate();
    return result;
  };

  return (
    <Box>
      <HStack>
        <Avatar
          variant="outline"
          src={user.uploadedProfileImage}
          name={user.name}
          aria-label={user.name}
          icon={<UserIcon />}
          color="primary.text.main"
          bgColor="transparent"
          borderColor="primary.bg.main"
          borderWidth="2px"
          css={{
            '& chakra-avatar__initials': {
              ...textStyles.h4,
            },
          }}
          mr={4}
          boxSize={16}
          cursor="pointer"
          _hover={{ opacity: 0.8 }}
          onClick={() => setIsModalOpen(true)}
        />
        <VStack align="start" flex={1} minW={0}>
          <Text textStyle="h5">Profile image</Text>
          {user.uploadedProfileImage === null ? (
            <Button
              size="sm"
              backgroundColor="primary.text.main"
              onClick={() => setIsModalOpen(true)}
            >
              <Icon>
                <UploadIcon />
              </Icon>
              Upload Image
            </Button>
          ) : (
            <HStack
              borderRadius="md"
              width={'100%'}
              px="2"
              backgroundColor="bg.level1"
              cursor="pointer"
              _hover={{ backgroundColor: 'bg.level2' }}
              onClick={() => setIsModalOpen(true)}
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
                _hover={{ cursor: 'pointer', color: 'primary.text.main' }}
              >
                <TrashIcon weight="fill" />
              </IconButton>
            </HStack>
          )}
        </VStack>
      </HStack>
      <UploadImageModal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCancel={() => setIsModalOpen(false)}
        onUploadSubmit={handleUploadSubmit}
      />
    </Box>
  );
}
