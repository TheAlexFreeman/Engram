import { VStack } from '@chakra-ui/react';
import { Outlet, createFileRoute } from '@tanstack/react-router';

import MainFooter from '@/components/layout/footer/MainFooter';
import AuthenticatedNavbar from '@/components/layout/navbar/AuthenticatedNavbar';

export const Route = createFileRoute('/_auth')({
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  return (
    <VStack minH="100vh" minW="fit-content" align="stretch">
      <AuthenticatedNavbar w="100%" mb="10" />
      <Outlet />
      <MainFooter />
    </VStack>
  );
}
