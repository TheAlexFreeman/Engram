import { useCallback, useMemo, useState } from 'react';

import { Badge, Box, HStack, Icon, IconButton, Input, Link, Text, VStack } from '@chakra-ui/react';
import {
  Plus as AddIcon,
  CaretCircleRight as CaretIcon,
  UsersFour as TeamIcon,
  User as UserIcon,
  X,
} from '@phosphor-icons/react';
import { Link as RouterLink, createFileRoute } from '@tanstack/react-router';
import { useAtomValue } from 'jotai';

import { AccountType } from '@/api/types/accounts/accounts';
import { Membership, Role } from '@/api/types/accounts/memberships';
import { Avatar } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { InputGroup } from '@/components/ui/input-group';
import { toaster } from '@/components/ui/toaster';
import accountService from '@/services/accounts';
import { membershipsAtom } from '@/state/auth';

export const Route = createFileRoute('/_auth/settings/accounts')({
  component: Accounts,
});

function Accounts() {
  const allMemberships = useAtomValue(membershipsAtom);
  // NOTE: At the time of writing, we're assuming that there's always a personal
  // membership present.
  const personalMembership = useMemo<Membership>(() => {
    const filtered = allMemberships.filter((m) => m.account.accountType === AccountType.PERSONAL);
    return filtered[0];
  }, [allMemberships]);
  const teamMemberships = useMemo<Membership[]>(() => {
    return allMemberships.filter((m) => m.account.accountType === AccountType.TEAM);
  }, [allMemberships]);

  const [actionLoading, setActionLoading] = useState<'create' | null>(null);

  const [isCreating, setIsCreating] = useState(false);
  const [accountCreatingName, setAccountCreatingName] = useState('');

  const handleCreate = useCallback(async () => {
    if (actionLoading === 'create') return;

    let wasSuccessful = false;
    try {
      setActionLoading('create');

      const accountPromise = accountService.create({
        name: accountCreatingName,
        accountType: AccountType.TEAM,
      });
      toaster.promise(accountPromise, {
        success: {
          title: `Success`,
          description: `Account ${accountCreatingName} created successfully.`,
        },
        error: { title: 'Error', description: 'Something went wrong creating the new account.' },
        loading: { title: 'Loading', description: 'Account creation in progress...' },
      });
      await accountPromise;
      wasSuccessful = true;
    } finally {
      setActionLoading(null);
    }

    if (wasSuccessful) {
      setIsCreating(false);
      setAccountCreatingName('');
    }
  }, [actionLoading, accountCreatingName]);

  const userMemberships = useMemo(
    () => [personalMembership, ...teamMemberships],
    [personalMembership, teamMemberships],
  );

  return (
    <>
      <Text textStyle="h3">Accounts</Text>
      {userMemberships.map((membership) => (
        <AccountCard key={membership.id} membership={membership} />
      ))}

      {isCreating ? (
        <HStack>
          <InputGroup
            border="none"
            endElement={
              <Icon
                role="button"
                boxSize="20px"
                cursor="pointer"
                aria-label="Remove and Clear"
                onClick={() => {
                  setAccountCreatingName('');
                  setIsCreating(false);
                }}
              >
                <X />
              </Icon>
            }
          >
            <Input
              id="input-create-account"
              placeholder="New Account Name"
              variant="flushed"
              value={accountCreatingName}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setAccountCreatingName(e.target.value);
              }}
              disabled={actionLoading === 'create'}
            />
          </InputGroup>
          <Button
            loading={actionLoading === 'create'}
            onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
              e.preventDefault();
              void handleCreate();
            }}
          >
            Create
          </Button>
        </HStack>
      ) : (
        <Button
          justifyContent="flex-start"
          p="1.5"
          variant="ghost"
          onClick={() => {
            setIsCreating(true);
            setTimeout(() => {
              document.getElementById('input-create-account')?.focus();
            }, 0);
          }}
        >
          <AddIcon />
          Create Account
        </Button>
      )}
    </>
  );
}

function AccountCard({ membership }: { membership: Membership }) {
  const { account, role } = membership;

  const isTeamAccount = useMemo(
    () => account.accountType === AccountType.TEAM,
    [account.accountType],
  );

  const [caretIconColor, setCaretIconColor] = useState<'gray' | 'black'>('gray');

  return (
    <Link asChild colorPalette="primary" className="group">
      <RouterLink
        to={`/accounts/$accountId/${isTeamAccount ? 'team' : 'settings'}`}
        params={{ accountId: account.id.toString() }}
        style={{ textDecoration: 'none' }}
        viewTransition
      >
        <Box
          borderRadius="md"
          p={4}
          mb={2}
          width={400}
          borderColor="neutral.100"
          borderWidth="1px"
          cursor="pointer"
          css={{
            '&:hover': {
              shadow: 'md',
              p: { color: 'primary.text.main' },
            },
          }}
          _hover={{ borderColor: 'primary.text.main', color: 'primary.text.main' }}
          onMouseOver={() => setCaretIconColor('black')}
          onMouseOut={() => setCaretIconColor('gray')}
        >
          <HStack justifyContent="space-between">
            <HStack>
              <Avatar
                variant="outline"
                size="sm"
                src={account.uploadedProfileImage}
                name={account.displayName}
                borderColor="primary.text.light"
                borderWidth="2px"
                bg="transparent"
                color="primary.text.main"
                _groupHover={{ color: 'primary.text.main' }}
              />
              <VStack gap="1" justify="flex-start" align="flex-start">
                <Text textStyle="h4">{account.displayName} </Text>
                <Text
                  textStyle="body2"
                  color="text.lighter"
                  display="flex"
                  alignItems="center"
                  gap="1"
                  _groupHover={{ color: 'primary.text.main' }}
                >
                  <Icon fontSize="1rem">
                    {isTeamAccount ? <TeamIcon weight="fill" /> : <UserIcon weight="fill" />}
                  </Icon>{' '}
                  {isTeamAccount ? 'Team' : 'Personal'} Account
                  {isTeamAccount && role === Role.OWNER && (
                    <Badge
                      color="purple.500"
                      p="1"
                      borderRadius="xl"
                      textStyle="chipXS"
                      textTransform="none"
                    >
                      Owner
                    </Badge>
                  )}
                </Text>
              </VStack>
            </HStack>

            <IconButton
              rounded="full"
              variant="ghost"
              colorPalette="gray"
              aria-label={`Go to ${isTeamAccount ? 'Team' : 'Personal'} Account `}
              background="transparent"
            >
              <CaretIcon weight="fill" color={caretIconColor} fontSize="1.5rem" />
            </IconButton>
          </HStack>
        </Box>
      </RouterLink>
    </Link>
  );
}
