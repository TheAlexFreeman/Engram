import { useState } from 'react';

import { HStack, Icon, Link, Text } from '@chakra-ui/react';
import ChevronDownIcon from '@heroicons/react/24/solid/ChevronDownIcon';
import ChevronUpIcon from '@heroicons/react/24/solid/ChevronUpIcon';
import { Gear as GearIcon, Plus as PlusIcon, User as UserIcon } from '@phosphor-icons/react';
import { Link as RouterLink, useMatchRoute, useRouter } from '@tanstack/react-router';
import { useAtom, useAtomValue } from 'jotai';

import { AccountType } from '@/api/types/accounts/accounts';
import { Membership } from '@/api/types/accounts/memberships';
import { Avatar } from '@/components/ui/avatar';
import { MenuContent, MenuItem, MenuRoot, MenuTrigger } from '@/components/ui/menu';
import { authUserAtom, currentMembershipAtom, membershipsAtom } from '@/state/auth';

function AccountDropdown() {
  const router = useRouter();

  const user = useAtomValue(authUserAtom);

  const [currentMembership, setCurrentMembership] = useAtom(currentMembershipAtom) as [
    NonNullable<Membership>,
    (membership: Membership) => void,
  ];
  const memberships = useAtomValue(membershipsAtom);

  const [displayAccountList, setDisplayAccountList] = useState(false);

  const matchRoute = useMatchRoute();

  const handleAccountClick = (membership: Membership) => {
    setCurrentMembership(membership);

    const { id, accountType } = membership.account;

    const currentPath = location.pathname;
    const pattern = /^\/accounts\/([^/]+)/;
    let newPath = currentPath.replace(pattern, `/accounts/${id}`);

    // If switching from a team account to a personal account, remove the `/team` part
    // from the URL, which will then redirect to the account's `settings` page.
    const currentRouteMatch = matchRoute({ to: '/accounts/$accountId/team' });
    if (currentRouteMatch && currentRouteMatch.accountId && accountType === AccountType.PERSONAL) {
      newPath = newPath.replace('/team', '');
    }

    router.history.replace(newPath);
    void router.invalidate();
  };

  return (
    <MenuRoot closeOnSelect>
      <MenuTrigger>
        <Avatar
          size="sm"
          src={user.uploadedProfileImage}
          name={user.name || user.email}
          borderColor="primary.text.light"
          borderWidth="2px"
          bg="transparent"
          color="primary.text.main"
          cursor="pointer"
        />
      </MenuTrigger>
      <MenuContent pt={0}>
        {displayAccountList ? (
          <>
            <MenuItem
              key={`current_in_list__${currentMembership.id ?? -1}`}
              closeOnSelect={false}
              onClick={() => setDisplayAccountList(!displayAccountList)}
              background="bg.level1"
              value="membership-current"
            >
              <Avatar
                variant="outline"
                size="sm"
                src={currentMembership.account.uploadedProfileImage}
                name={currentMembership.account.displayName}
                borderColor="primary.text.light"
                borderWidth="2px"
                bg="transparent"
                color="primary.text.main"
              />
              <HStack>
                <Text>{currentMembership.account.displayName}</Text>
                <Icon size="sm">
                  <ChevronUpIcon />
                </Icon>
              </HStack>
            </MenuItem>
            {memberships.map((membership) => (
              <MenuItem
                key={membership.id}
                value={`membership-id-${membership.id}`}
                onClick={() => handleAccountClick(membership)}
                borderRadius={24}
                p={2}
                m={1}
                width="95%"
                alignItems="center"
                display="flex"
                cursor="pointer"
                background={
                  membership.id === currentMembership.id ? 'primary.bg.light' : 'transparent'
                }
                _hover={{
                  bg:
                    membership.id === currentMembership.id
                      ? 'primary.bg.light'
                      : 'primary.bg.lighter',
                }}
              >
                <Avatar
                  variant="outline"
                  size="sm"
                  src={membership.account.uploadedProfileImage}
                  name={membership.account.displayName}
                  borderColor="primary.text.light"
                  borderWidth="2px"
                  bg="transparent"
                  color="primary.text.main"
                  mr={2}
                />
                {membership.account.displayName}
              </MenuItem>
            ))}
            <MenuItem asChild key="create" cursor="pointer" value="account-create">
              <Link
                asChild
                _hover={{ textDecoration: 'none' }}
                _active={{ textDecoration: 'none' }}
              >
                <RouterLink to="/settings/accounts">
                  <Icon color="text.lighter" fontSize="1rem">
                    <PlusIcon />
                  </Icon>
                  Create Account
                </RouterLink>
              </Link>
            </MenuItem>
          </>
        ) : (
          <>
            <MenuItem
              key={`current_not_in_list__${currentMembership.id ?? -1}`}
              closeOnSelect={false}
              onClick={() => setDisplayAccountList(!displayAccountList)}
              background="bg.level1"
              value={currentMembership.id.toString()}
              cursor="pointer"
            >
              <Avatar
                variant="outline"
                size="sm"
                src={currentMembership.account.uploadedProfileImage}
                name={currentMembership.account.displayName}
                borderColor="primary.text.light"
                borderWidth="2px"
                bg="transparent"
                color="primary.text.main"
              />
              <HStack>
                <Text>{currentMembership.account.displayName}</Text>
                <Icon size="sm">
                  <ChevronDownIcon />
                </Icon>
              </HStack>
            </MenuItem>

            <MenuItem
              asChild
              key="account"
              px={4}
              py={2}
              m={1}
              value="account-settings"
              cursor="pointer"
            >
              <Link
                asChild
                _hover={{ textDecoration: 'none' }}
                _active={{ textDecoration: 'none' }}
              >
                <RouterLink to="/accounts/$accountId/settings" params={{ accountId: 'current' }}>
                  <Icon color="text.lighter">
                    <GearIcon weight="fill" fontSize="1rem" />
                  </Icon>
                  Account settings
                </RouterLink>
              </Link>
            </MenuItem>
            <MenuItem
              asChild
              key="user"
              px={4}
              py={2}
              m={1}
              value="global-settings"
              cursor="pointer"
            >
              <Link
                asChild
                _hover={{ textDecoration: 'none' }}
                _active={{ textDecoration: 'none' }}
              >
                <RouterLink to="/settings/profile">
                  <Icon color="text.lighter">
                    <UserIcon weight="fill" fontSize="1rem" />
                  </Icon>
                  Global Settings
                </RouterLink>
              </Link>
            </MenuItem>
            <MenuItem
              asChild
              key="logout"
              value="logout"
              justifyContent="center"
              color="fg.error"
              _hover={{
                bg: 'bg.error',
              }}
              _active={{
                bg: 'bg.error',
              }}
              cursor="pointer"
            >
              <Link
                asChild
                _hover={{ textDecoration: 'none' }}
                _active={{ textDecoration: 'none' }}
              >
                <RouterLink to="/settings/logout">Log out</RouterLink>
              </Link>
            </MenuItem>
          </>
        )}
      </MenuContent>
    </MenuRoot>
  );
}

export default AccountDropdown;
