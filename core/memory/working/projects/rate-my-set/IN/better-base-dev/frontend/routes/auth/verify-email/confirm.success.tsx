import { useEffect } from 'react';

import { Box, Container, Heading, VStack } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import EmailVerifiedIllustration from '@/assets/illustrations/EmailVerifiedIllustration';
import { Button } from '@/components/ui/button';
import { userAtom } from '@/state/auth';

export const Route = createFileRoute('/auth/verify-email/confirm/success')({
  component: SignupVerifyEmailSuccess,
});

function SignupVerifyEmailSuccess() {
  const user = useAtomValue(userAtom);
  const redirectTo = user.isAuthenticated ? '/auth/signup/complete' : '/auth/login';

  useEffect(() => {
    let channel: BroadcastChannel | null = null;

    if (typeof window !== 'undefined' && window.BroadcastChannel) {
      channel = new BroadcastChannel('significantEvents');
      channel.postMessage({ eventType: 'user.emailVerified' });
    }

    return () => {
      if (channel != null) {
        channel.close();
      }
    };
  }, []);

  return (
    <Container maxW="max(150px, 60ch)" centerContent mt="20">
      <Box mb="10">
        <EmailVerifiedIllustration />
      </Box>
      <VStack gap="5">
        <Heading as="h1" textStyle="h2">
          Thank you for verifying your email!
        </Heading>
        <Heading as="h2" textStyle="h4">
          {user.isAuthenticated &&
            'Please close this tab and return to your original tab or continue here.'}
          {!user.isAuthenticated &&
            'Please close this tab and return to your original tab to continue or log in here.'}
        </Heading>
        <Button asChild variant="ghost">
          <RouterLink to={redirectTo}>{user.isAuthenticated ? 'Continue' : 'Log In'}</RouterLink>
        </Button>
      </VStack>
    </Container>
  );
}
