import { Link, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from '@tanstack/react-router';

import { Button } from '@/components/ui/button';

import UserEditPasswordForm from './UserEditPasswordForm';

export default function UserEditPasswordSection() {
  return (
    <VStack
      bgColor="bg.level1"
      borderRadius={16}
      alignItems="flex-start"
      p={6}
      gap={6}
      width="full"
    >
      <Text textStyle="h3">Reset Password</Text>
      <UserEditPasswordForm />
      <Button asChild variant="plain" pl="0" color="primary.text.main">
        <Link asChild>
          <RouterLink to="/auth/reset-password" viewTransition>
            Forgot password?
          </RouterLink>
        </Link>
      </Button>
    </VStack>
  );
}
