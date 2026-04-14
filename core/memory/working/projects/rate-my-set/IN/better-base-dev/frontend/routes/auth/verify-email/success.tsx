import { useEffect } from 'react';

import { Box, Container, Heading, VStack } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import EmailVerifiedIllustration from '@/assets/illustrations/EmailVerifiedIllustration';
import { Button } from '@/components/ui/button';
import { toaster } from '@/components/ui/toaster';
import { userAtom } from '@/state/auth';

export const Route = createFileRoute('/auth/verify-email/success')({
  component: VerifyEmailSuccess,
});

function VerifyEmailSuccess() {
  const user = useAtomValue(userAtom);
  const redirectTo = user.isAuthenticated ? '/auth/signup/complete' : '/auth/login';
  const navigate = Route.useNavigate();

  useEffect(() => {
    const handleFocus = () => {
      if (document.visibilityState === 'visible') {
        toaster.create({
          title: 'Verified',
          description: 'Your email has been verified.',
          type: 'success',
          duration: 7000,
          meta: { closable: true },
        });
        void navigate({ to: redirectTo });
      }
    };

    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('visibilitychange', handleFocus, false);
    }

    return () => {
      window.removeEventListener('visibilitychange', handleFocus);
    };
  }, [navigate, redirectTo]);

  return (
    <Container maxW="max(150px, 60ch)" centerContent mt="20">
      <Box mb="10">
        <EmailVerifiedIllustration />
      </Box>
      <VStack gap="5">
        <Heading as="h1" textStyle="h2">
          Thank you for verifying your email!
        </Heading>
        <Button asChild variant="solidInverse">
          <RouterLink to={redirectTo}>Continue</RouterLink>
        </Button>
      </VStack>
    </Container>
  );
}
