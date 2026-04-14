import { useCallback, useEffect, useMemo } from 'react';

import { Box, HStack, Link, Spacer, Text, VStack } from '@chakra-ui/react';
import { QueryClient, useQueryErrorResetBoundary } from '@tanstack/react-query';
import {
  Outlet,
  Link as RouterLink,
  createRootRouteWithContext,
  isNotFound,
  useRouter,
} from '@tanstack/react-router';

import { NotFoundError, PermissionsError, ServerError } from '@/api/types/api';
import dotsUrl from '@/assets/illustrations/Dots.svg';
import ellipseUrl from '@/assets/illustrations/Ellipse1.svg';
import { Button } from '@/components/ui/button';
import DefaultNotFoundComponent from '@/DefaultNotFoundComponent';
import TanStackRouterDevtools from '@/devtools/tanstackRouterDevtools';

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootRoute,
  errorComponent: RootErrorComponent,
});

function RootRoute() {
  return (
    <>
      <Outlet />
      <TanStackRouterDevtools />
    </>
  );
}

type RootErrorComponentProps = {
  error: Error;
  reset: () => void;
};

function RootErrorComponent({ error, reset }: RootErrorComponentProps) {
  const router = useRouter();
  const queryErrorResetBoundary = useQueryErrorResetBoundary();

  const backgroundProps = useMemo(
    () => ({
      w: '100%',
      backgroundImage: `url("${dotsUrl}")`,
      backgroundRepeat: 'no-repeat',
      minH: '100vh',
    }),
    [],
  );

  const stackProps = useMemo(
    () => ({
      gap: '2',
      maxW: '450px',
      py: '20',
      margin: 'auto',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
    }),
    [],
  );

  const mainTextProps = useMemo(
    () => ({
      fontSize: '116px',
      fontWeight: '600',
      bgClip: 'text',
      bgGradient: 'linear(#7772FF, #434099, rgba(31, 28, 104, 0.72))',
    }),
    [],
  );

  useEffect(() => {
    // Reset the query error boundary.
    // (See https://tanstack.com/router/latest/docs/framework/react/guide/external-data-loading#error-handling-with-tanstack-query)
    queryErrorResetBoundary.reset();
  }, [queryErrorResetBoundary]);

  const handleTryAgain = useCallback(() => {
    // https://tanstack.com/router/latest/docs/framework/react/guide/data-loading#handling-errors-with-routeoptionserrorcomponent
    // Reset the router error boundary.
    reset();
    // Invalidate the route to reload the loader
    void router.invalidate();
  }, [reset, router]);

  if (error instanceof PermissionsError) {
    return (
      <Box {...backgroundProps}>
        <VStack {...stackProps}>
          <Text {...mainTextProps}>403</Text>
          <VStack alignItems="inherit">
            <Text textStyle="body1" mt="-8">
              Sorry, you do not have access to this page.
            </Text>
            <Spacer />
            <Button p="2" asChild>
              <Link asChild>
                <RouterLink to="/">Back to home</RouterLink>
              </Link>
            </Button>
          </VStack>
          <Box bgImage={`url("${ellipseUrl}")`} w="287px" h="18px" ml="-16" mt="4" />
        </VStack>
      </Box>
    );
  }

  if (
    error instanceof NotFoundError ||
    isNotFound(error) ||
    (error as unknown as { status: number })?.status == 404
  ) {
    return <DefaultNotFoundComponent />;
  }

  if (error instanceof ServerError) {
    return (
      <Box {...backgroundProps}>
        <VStack {...stackProps}>
          <Text {...mainTextProps}>Oh dear.</Text>
          <VStack alignItems="inherit">
            <Text textStyle="body1" mt="-8">
              Our system encountered an unexpected error. Our team has been notified and are
              actively looking into it. If the problem persists, please email{' '}
              <Link color="primary.text.main" href="mailto:support@betterbase.com">
                support@betterbase.com
              </Link>
              .
            </Text>
            <Spacer />
            <HStack>
              <Button p="2" onClick={handleTryAgain}>
                Try again
              </Button>
              <Link color="primary.text.main" asChild>
                <RouterLink to="/">Go to home</RouterLink>
              </Link>
            </HStack>
          </VStack>
          <Box bgImage={`url("${ellipseUrl}")`} w="287px" h="18px" ml="-16" mt="4" />
        </VStack>
      </Box>
    );
  }

  return (
    <Box {...backgroundProps}>
      <VStack {...stackProps}>
        <Text {...mainTextProps}>500</Text>
        <Text textStyle="h2" mt="-8">
          Oh dear.
        </Text>
        <VStack alignItems="inherit">
          <Text textStyle="body1">
            Our system encountered an unexpected error. Our team has been notified and are actively
            looking into it. If the problem persists, please email{' '}
            <Link color="primary.text.main" href="mailto:support@betterbase.com">
              support@betterbase.com
            </Link>
            .
          </Text>
          <Spacer />
          <HStack>
            <Button p="2" onClick={handleTryAgain}>
              Try again
            </Button>
            <Link color="primary.text.main" asChild>
              <RouterLink to="/">Go to home</RouterLink>
            </Link>
          </HStack>
        </VStack>
        <Box bgImage={`url("${ellipseUrl}")`} w="287px" h="18px" ml="-16" mt="4" />
      </VStack>
    </Box>
  );
}
