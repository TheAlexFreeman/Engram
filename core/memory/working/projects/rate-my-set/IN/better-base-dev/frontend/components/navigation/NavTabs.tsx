import { Link, List, type ListItemProps, type ListRootProps } from '@chakra-ui/react';
import { Link as RouterLink } from '@tanstack/react-router';

import { Button } from '@/components/ui/button';

export type NavTabItem = {
  id: string;
  label: string;
  to: string;
  params: { [name: string]: string | undefined };
  isActive: boolean;
  clickNavigator: () => void;
} & ListItemProps;

export type NavTabsProps = {
  variant: 'solid';
  direction: 'vertical' | 'horizontal';
  items: NavTabItem[];
} & ListRootProps;

export default function NavTabs({ direction, items, ...rest }: NavTabsProps) {
  const { css: restCss, ...remaining } = rest;

  const flexDirection = direction === 'vertical' ? 'column' : 'row';
  const flexWrap = direction === 'vertical' ? 'nowrap' : 'wrap';
  const gap = '5';

  const liWidth = direction === 'vertical' ? '100%' : 'auto';
  const liPx = direction === 'vertical' ? '2' : '2';
  const liPy = direction === 'vertical' ? '0' : '0';

  return (
    <List.Root
      display="flex"
      flexDirection={flexDirection}
      flexWrap={flexWrap}
      gap={gap}
      bgColor="bg.level1"
      borderRadius="xl"
      p="1"
      css={{
        ...{
          '& .accountItem': {
            transitionProperty: 'common',
            transitionDuration: 'fast',
            borderRadius: 'xl',
            cursor: 'pointer',

            '&:hover, &:active': {
              '&, &.accountLink': {
                bgColor: 'bg.level2',
              },
            },

            '&:focus-visible': {
              boxShadow: 'outline',
            },
          },
          '& .accountItem.isActive': {
            '&, &.accountLink': {
              color: 'text.inverse',
              bgColor: 'primary.bg.main',
            },
            '&:hover, &:active': {
              '&, &.accountLink': {
                color: 'text.inverse',
                bgColor: 'primary.bg.main',
              },
            },
          },
          '& .accountLink': {
            transitionProperty: 'common',
            transitionDuration: 'fast',
            '&:focus-visible': {
              boxShadow: 'outline',
            },
          },
        },
        ...restCss,
      }}
      {...remaining}
    >
      {items.map(({ id, isActive, clickNavigator, to, params, label, ...itemProps }) => (
        <List.Item
          key={id}
          className={isActive ? 'accountItem isActive' : 'accountItem'}
          onClick={clickNavigator}
          w={liWidth}
          px={liPx}
          py={liPy}
          {...itemProps}
        >
          <Button
            asChild
            variant="plain"
            className={isActive ? 'accountLink isActive' : 'accountLink'}
            color={isActive ? 'text.inverse' : 'text.main'}
            textStyle="h5"
            w="100%"
            textAlign="start"
            justifyContent="flex-start"
            mx="1"
            _hover={{ textDecoration: 'none' }}
            _active={{ textDecoration: 'none' }}
          >
            <Link asChild>
              <RouterLink to={to} params={params} viewTransition>
                {label}
              </RouterLink>
            </Link>
          </Button>
        </List.Item>
      ))}
    </List.Root>
  );
}
