import { useCallback, useEffect, useRef, useState } from 'react';

import { Box, HStack, Heading, Icon, Link, VStack } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import ArrowPathIcon from '@heroicons/react/24/solid/ArrowPathIcon';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { InitialData } from '@/api/types/initialData';
import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import { wrapRequestWithErrorHandling } from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authService from '@/services/auth';
import { userAtom } from '@/state/auth';
import { getBestSingleErrorMessageFor } from '@/utils/errors';

export const Route = createFileRoute('/auth/verify-email/sent')({
  component: VerifyEmailSent,
});

function VerifyEmailSent() {
  const navigate = Route.useNavigate();

  const user = useAtomValue(userAtom);
  const { email: initialEmail } = user.isAuthenticated ? user : { email: '' };

  const navigatePostVerification = useCallback(
    ({ inBackground }: { inBackground: boolean }) => {
      if (inBackground) {
        void navigate({ from: Route.fullPath, to: '../success', viewTransition: true });
      } else if (user.isAuthenticated) {
        void navigate({ to: '/auth/signup/complete' });
      } else {
        void navigate({ to: '/auth/login', viewTransition: true });
      }
    },
    [navigate, user.isAuthenticated],
  );

  const refreshRef = useRef<{ inProgress: boolean }>({ inProgress: false });
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const refresh = useCallback(
    async ({ inBackground }: { inBackground: boolean }) => {
      let data: InitialData | null | undefined = null;

      if (refreshRef.current.inProgress) return;

      try {
        refreshRef.current.inProgress = true;
        setIsRefreshing(true);

        const request = authService.refreshMe();
        const wrapped = await wrapRequestWithErrorHandling({ awaitable: request });

        if (wrapped.hasError) {
          const errorMessage = getBestSingleErrorMessageFor(wrapped.error);

          toaster.create({
            title: 'Failed to Refresh Verification Status',
            description: errorMessage,
            type: 'error',
            duration: 10000,
            meta: { closable: true },
          });
        } else {
          data = wrapped.result;
        }
      } finally {
        refreshRef.current.inProgress = false;
        setIsRefreshing(false);
      }

      if (data != null) {
        if (data.user.isAuthenticated && data.user.emailIsVerified) {
          toaster.create({
            title: 'Verified',
            description: 'Your email has been verified.',
            type: 'success',
            duration: 7000,
            meta: { closable: true },
          });
          navigatePostVerification({ inBackground });
        } else if (!inBackground && initialEmail) {
          const refreshedEmailValue = data.user.isAuthenticated ? data.user.email : initialEmail;
          toaster.create({
            title: 'Not Yet Verified',
            description: `Your email has not been verified yet (${refreshedEmailValue}).`,
            type: 'warning',
            duration: 10000,
            meta: { closable: true },
          });
        }
      }
    },
    [initialEmail, navigatePostVerification],
  );

  const handleRefreshClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      void refresh({ inBackground: false });
    },
    [refresh],
  );

  useEffect(() => {
    const originHere = window.location.origin;
    const channel = new BroadcastChannel('significantEvents');

    const onMessage = (event: MessageEvent): void => {
      const { data, origin } = event;

      if (!user.isAuthenticated) return;
      if (origin !== originHere) return;
      if (typeof data !== 'object') return;

      if (data?.eventType === 'user.emailVerified') {
        void refresh({ inBackground: true });
      }
    };

    channel.addEventListener('message', onMessage, false);

    return () => {
      channel.removeEventListener('message', onMessage);
      channel.close();
    };
  }, [user.isAuthenticated, refresh]);

  return (
    <FullCentered>
      <FullCenteredPanel
        top={
          <VStack gap={4} mb="4" alignItems="stretch" width="100%">
            <HStack width="100%">
              <Box w="41px" h="32px">
                <MainLogo />
              </Box>
            </HStack>
            <VStack width="100%" alignItems="flex-start">
              <Heading as="h1" textStyle="h2">
                Sent!
              </Heading>
              <Heading as="h2" textStyle="body1">
                Check your email. We&apos;ve sent you a link to verify your email.
              </Heading>
            </VStack>
            <VStack gap={4} alignItems="flex-start">
              {user.isAuthenticated && (
                <Button onClick={handleRefreshClick} disabled={isRefreshing} loading={isRefreshing}>
                  Refresh Status
                  <Icon>
                    <ArrowPathIcon />
                  </Icon>
                </Button>
              )}
              <Button asChild variant="ghost">
                <Link asChild _hover={{ textDecoration: 'none' }}>
                  <RouterLink to={'/auth/verify-email'} viewTransition>
                    Resend
                  </RouterLink>
                </Link>
              </Button>
            </VStack>
          </VStack>
        }
        bottom={
          <Button asChild variant="plain" w="100%">
            <Link asChild>
              <RouterLink to={'/auth/login'} viewTransition>
                <Icon>
                  <ChevronLeftIcon />
                </Icon>
                Back to log in
              </RouterLink>
            </Link>
          </Button>
        }
      />
    </FullCentered>
  );
}
