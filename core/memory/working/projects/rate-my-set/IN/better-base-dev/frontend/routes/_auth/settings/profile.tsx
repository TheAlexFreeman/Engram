import { Heading, VStack } from '@chakra-ui/react';
import { createFileRoute } from '@tanstack/react-router';

import ProfileImageSection from '@/components/settings/sections/ProfileImageSection';
import UserDeleteSection from '@/components/settings/sections/UserDeleteSection';
import UserEditEmailSection from '@/components/settings/sections/UserEditEmailSection';
import UserEditNameSection from '@/components/settings/sections/UserEditNameSection';
import UserEditPasswordSection from '@/components/settings/sections/UserEditPasswordSection';

export const Route = createFileRoute('/_auth/settings/profile')({
  component: Profile,
});

function Profile() {
  return (
    <VStack alignItems="stretch" w="100%" gap="6">
      <Heading as="h2" textStyle="h3">
        Profile
      </Heading>
      <ProfileImageSection />
      <UserEditNameSection />
      <UserEditEmailSection />
      <UserEditPasswordSection />
      <UserDeleteSection />
    </VStack>
  );
}
