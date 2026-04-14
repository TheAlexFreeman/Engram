import { useMemo } from 'react';

import { Container, Heading, VStack } from '@chakra-ui/react';
import { Outlet, createFileRoute, useLocation, useNavigate } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import NavTabs, { NavTabItem } from '@/components/navigation/NavTabs';
import { Avatar } from '@/components/ui/avatar';
import { authUserAtom } from '@/state/auth';
import { textStyles } from '@/theme/text-styles';

export const Route = createFileRoute('/_auth/settings')({
  component: UserSettings,
});

function UserSettings() {
  const location = useLocation();
  const navigate = useNavigate();

  const user = useAtomValue(authUserAtom);

  const items = useMemo<NavTabItem[]>(() => {
    const initial = [
      { id: 'accounts', label: 'Accounts', to: '/settings/accounts', params: {} },
      { id: 'profile', label: 'Profile', to: '/settings/profile', params: {} },
      {
        id: 'logout',
        label: 'Log out',
        to: '/settings/logout',
        params: {},
        css: {
          '&.accountItem.isActive': {
            bgColor: 'danger.solid',
            color: 'text.inverse',
            '&:hover, &:active': {
              bgColor: '{colors.danger.solid/90}',
              color: 'text.inverse',
              '& .accountLink.isActive': {
                bgColor: '{colors.danger.solid/90}',
                color: 'text.inverse',
              },
            },
            '& .accountLink.isActive': {
              bgColor: 'transparent',
              color: 'text.inverse',
              '&:hover, &:active': {
                bgColor: 'transparent',
                color: 'text.inverse',
              },
            },
          },
        },
      },
    ];

    return initial.map((data) => ({
      ...data,
      isActive: location.pathname.indexOf(data.id) > 0,
      clickNavigator: () => {
        void navigate({ to: data.to, viewTransition: true });
      },
    }));
  }, [location.pathname, navigate]);

  return (
    <Container maxW="max(150px, 60ch)" centerContent mt="10">
      <VStack gap="4" align="stretch">
        <VStack justify="center" align="center">
          <Avatar
            variant="outline"
            src={user.uploadedProfileImage}
            name={user.name || user.email}
            color="primary.text.main"
            bgColor="transparent"
            borderColor="primary.bg.main"
            borderWidth="2px"
            css={{
              '& chakra-avatar__initials': {
                ...textStyles.h4,
              },
            }}
          />
        </VStack>
        <VStack align="center">
          <Heading as="h2" textStyle="h2">
            User Settings
          </Heading>
        </VStack>
        <VStack align="center">
          <NavTabs variant="solid" direction="horizontal" items={items} mb="8" />
        </VStack>
        <Outlet />
      </VStack>
    </Container>
  );
}
