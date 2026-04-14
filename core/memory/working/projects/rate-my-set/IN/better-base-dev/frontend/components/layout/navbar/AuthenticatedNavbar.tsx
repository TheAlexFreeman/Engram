import { useMemo } from 'react';

import { Box, Flex, HStack, type StackProps } from '@chakra-ui/react';
import { Link as RouterLink } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import NavbarLogo from '@/components/logos/NavbarLogo';
import { userAtom } from '@/state/auth';

import AccountDropdown from './AccountDropdown';
import ColorModeToggle from './ColorModeToggle';

export type AuthenticatedNavbarProps = StackProps;

function AuthenticatedNavbar(props: AuthenticatedNavbarProps) {
  const user = useAtomValue(userAtom);
  const isAuthenticated = useMemo(() => user.isAuthenticated, [user.isAuthenticated]);

  return (
    <HStack w="100%" h="3rem" align="center" gap="3" px="3" py="3" bgColor="bg.level1" {...props}>
      <Box justifySelf="flex-start">
        <Flex justify="center" align="center" w="2rem" h="2rem">
          <RouterLink to="/">
            <NavbarLogo />
          </RouterLink>
        </Flex>
      </Box>
      <Box justifySelf="flex-end" ms="auto">
        <HStack>
          <ColorModeToggle />
          {isAuthenticated && <AccountDropdown />}
        </HStack>
      </Box>
    </HStack>
  );
}

export default AuthenticatedNavbar;
