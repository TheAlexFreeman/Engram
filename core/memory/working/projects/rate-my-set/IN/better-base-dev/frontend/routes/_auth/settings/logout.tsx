import { useCallback, useEffect, useRef, useState } from 'react';

import { Container, Heading, VStack } from '@chakra-ui/react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import authService from '@/services/auth';
import { userAtom } from '@/state/auth';

export const Route = createFileRoute('/_auth/settings/logout')({
  component: Logout,
});

function Logout() {
  const navigate = useNavigate();

  const user = useAtomValue(userAtom);

  const [shouldShow, setShouldShow] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const isLoadingRef = useRef<{ isLoading: boolean }>({ isLoading: false });
  const isLoggedOutRef = useRef<boolean>(false);

  const handleLogoutClick = useCallback(async () => {
    if (isLoadingRef.current.isLoading) return;

    try {
      isLoadingRef.current.isLoading = true;
      setIsLoading(true);

      await authService.logout();
      isLoggedOutRef.current = true;

      toaster.create({
        title: 'Logout Successful.',
        description: 'You have successfully logged out of your account.',
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });
      void navigate({ to: '/auth/login' });
    } finally {
      isLoadingRef.current.isLoading = false;
      setIsLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    if (user.isAuthenticated) {
      setShouldShow(true);
    }
    if (!user.isAuthenticated && !isLoadingRef.current.isLoading && !isLoggedOutRef.current) {
      isLoggedOutRef.current = true;
      toaster.create({
        title: 'Already Logged Out',
        description: 'You were already logged out.',
        type: 'info',
        duration: 7000,
        meta: { closable: true },
      });
      void navigate({ to: '/auth/login' });
    }
  }, [user.isAuthenticated, navigate]);

  if (!shouldShow) return <></>;

  return (
    <Container maxW="max(150px, 60ch)" centerContent>
      <VStack gap={4} alignItems="stretch" w="100%">
        <Heading as="h2" textStyle="h3">
          Log out
        </Heading>
        <Heading as="h3" textStyle="body2" mb="4" color="text.lighter">
          You will be logged out of all your accounts.
        </Heading>
        <Button
          disabled={isLoading}
          loading={isLoading}
          onClick={handleLogoutClick}
          variant="solid"
          colorPalette="red"
          w="100"
        >
          Log out
        </Button>
      </VStack>
    </Container>
  );
}
