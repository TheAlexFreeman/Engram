import { useCallback, useEffect, useMemo } from 'react';

import { Grid, GridItem, HStack, Heading, VStack } from '@chakra-ui/react';
import { Outlet, createFileRoute, useLocation, useNavigate } from '@tanstack/react-router';
import { useAtom } from 'jotai';

import { Account, AccountType } from '@/api/types/accounts/accounts';
import { Membership } from '@/api/types/accounts/memberships';
import NavTabs, { NavTabItem } from '@/components/navigation/NavTabs';
import { Avatar } from '@/components/ui/avatar';
import localMembershipsService from '@/services/localMemberships';
import { currentMembershipAtom } from '@/state/auth';
import { textStyles } from '@/theme/text-styles';

export const Route = createFileRoute('/_auth/accounts/$accountId')({
  component: AccountHome,
  loader: localAccountLoader,
});

function localAccountLoader({ params: { accountId } }: { params: { accountId: string } }): Account {
  if (accountId === 'current') {
    const membership = localMembershipsService.getCurrent();
    if (membership == null) {
      throw new Error(`No Membership found for current account`);
    }
    return membership.account;
  }

  const membership = localMembershipsService.getByAccountId(Number(accountId));
  if (membership == null) {
    throw new Error(`No Membership found for Account with id=${accountId}.`);
  }
  return membership.account;
}

function AccountHome() {
  const [currentMembership, setCurrentMembership] = useAtom(currentMembershipAtom) as [
    NonNullable<Membership>,
    (membership: Membership) => void,
  ];
  const currentAccountId = currentMembership.account.id;

  const { accountId: accountIdParam } = Route.useParams();
  const loadedAccount = Route.useLoaderData();

  const switchCurrentMembership = useCallback(() => {
    const m = localMembershipsService.getByAccountId(loadedAccount.id);
    if (m != null) {
      setCurrentMembership(m);
    }
  }, [loadedAccount.id, setCurrentMembership]);

  useEffect(() => {
    if (
      accountIdParam !== 'current' &&
      loadedAccount.id != null &&
      currentAccountId !== loadedAccount.id
    ) {
      switchCurrentMembership();
    }
  }, [accountIdParam, loadedAccount.id, currentAccountId, switchCurrentMembership]);

  return (
    <Grid
      px="4"
      // CV3M TODO: Did using the --chakra variables work?
      minW={{
        base: `calc(100% - (2 * var(--chakra-spacing-6)))`,
        md: `calc(100% - (2 * var(--chakra-spacing-4)))`,
      }}
      templateAreas={{
        base: `
        "spacer1"
        "menu"
        "spacer2"
        "content"
        "spacer3"
        `,
        md: `"spacer1 menu spacer2 content spacer3"`,
      }}
      templateRows={{
        base: `0px auto var(--chakra-spacing-4) auto var(--chakra-spacing-4)`,
        md: 'auto',
      }}
      templateColumns={{
        base: '100%',
        md: `var(--chakra-spacing-16) 12.5rem var(--chakra-spacing-16) 1fr var(--chakra-spacing-16)`,
        lg: `var(--chakra-spacing-16) 12.5rem var(--chakra-spacing-32) 1fr var(--chakra-spacing-16)`,
        xl: `var(--chakra-spacing-16) 12.5rem var(--chakra-spacing-32) 1fr var(--chakra-spacing-32)`,
      }}
    >
      <GridItem area="spacer1" />
      <GridItem area="menu" minW="120px">
        <AccountNavigator />
      </GridItem>
      <GridItem area="spacer2" />
      <GridItem area="content" minW="400px">
        <Outlet />
      </GridItem>
      <GridItem area="spacer3" />
    </Grid>
  );
}

function AccountNavigator() {
  const location = useLocation();
  const account = Route.useLoaderData();
  const { accountId } = Route.useParams();
  const navigate = useNavigate();

  const items = useMemo<NavTabItem[]>(() => {
    const initial = [
      {
        id: 'settings',
        label: 'Settings',
        to: '/accounts/$accountId/settings',
        params: { accountId },
      },
      account.accountType === AccountType.TEAM
        ? {
            id: 'team',
            label: 'Team',
            to: '/accounts/$accountId/team',
            params: { accountId },
          }
        : { id: 'profile', label: 'Profile', to: '/settings/profile', params: {} },
    ];

    return initial.map((data) => ({
      ...data,
      isActive: location.pathname.indexOf(data.id) > 0,
      clickNavigator: () => {
        void navigate({ to: data.to, params: data.params, viewTransition: true });
      },
    }));
  }, [accountId, account.accountType, location.pathname, navigate]);

  return (
    <VStack gap="4" align="stretch" maxW="1200px">
      <HStack gap="2">
        <Avatar
          variant="outline"
          src={account.uploadedProfileImage}
          name={account.displayName}
          aria-label={account.displayName}
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
        <Heading as="h2" textStyle="h4" p="0">
          {account.displayName}
        </Heading>
      </HStack>
      <NavTabs variant="solid" direction="vertical" gap={1.5} items={items} />
    </VStack>
  );
}
