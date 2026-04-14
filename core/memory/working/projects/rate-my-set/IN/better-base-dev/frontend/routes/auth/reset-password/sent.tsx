import { Box, HStack, Heading, Icon, Link, VStack } from '@chakra-ui/react';
import ChevronLeftIcon from '@heroicons/react/20/solid/ChevronLeftIcon';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';

import FullCentered from '@/components/layout/full/FullCentered';
import FullCenteredPanel from '@/components/layout/full/panels/FullCenteredPanel';
import MainLogo from '@/components/logos/MainLogo';
import { Button } from '@/components/ui/button';

export const Route = createFileRoute('/auth/reset-password/sent')({
  component: ResetPasswordSent,
});

function ResetPasswordSent() {
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
                Check your email. We&apos;ve sent you a link to reset your password.
              </Heading>
            </VStack>
            <VStack gap={4} alignItems="flex-start">
              <Button asChild variant="plain" pl="0">
                <Link asChild>
                  <RouterLink to="/auth/reset-password" viewTransition>
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
              <RouterLink to="/auth/login" viewTransition>
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
