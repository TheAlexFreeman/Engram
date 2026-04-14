import { useEffect } from 'react';

import { Box, Container, Heading, VStack } from '@chakra-ui/react';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';

import EmailVerifiedIllustration from '@/assets/illustrations/EmailVerifiedIllustration';
import { Button } from '@/components/ui/button';

export const Route = createFileRoute('/auth/change-email/confirm/success')({
  component: ChangeEmailConfirmSuccess,
});

function ChangeEmailConfirmSuccess() {
  useEffect(() => {
    let channel: BroadcastChannel | null = null;

    if (typeof window !== 'undefined' && window.BroadcastChannel) {
      channel = new BroadcastChannel('significantEvents');
      channel.postMessage({ eventType: 'user.emailChanged' });
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
          You have successfully changed your email!
        </Heading>
        <Heading as="h2" textStyle="h4">
          Please close this tab and return to your original tab to continue or continue here.
        </Heading>
        <Button asChild variant="ghost">
          <RouterLink to="/settings/profile">Continue</RouterLink>
        </Button>
      </VStack>
    </Container>
  );
}
