'use client';

import type { ButtonProps, TextProps } from '@chakra-ui/react';

import * as React from 'react';

import {
  Button,
  Pagination as ChakraPagination,
  IconButton,
  Text,
  createContext,
  usePaginationContext,
} from '@chakra-ui/react';
import { HiChevronLeft, HiChevronRight, HiMiniEllipsisHorizontal } from 'react-icons/hi2';

import { LinkButton } from './link-button';

interface ButtonVariantMap {
  current: ButtonProps['variant'];
  default: ButtonProps['variant'];
  ellipsis: ButtonProps['variant'];
}

type PaginationVariant = 'outline' | 'solid' | 'subtle';

interface ButtonVariantContext {
  size: ButtonProps['size'];
  variantMap: ButtonVariantMap;
  getHref?: (page: number) => string;
  getChildLink?: (page: number, render: React.ReactNode) => React.ReactNode;
}

const [RootPropsProvider, useRootProps] = createContext<ButtonVariantContext>({
  name: 'RootPropsProvider',
});

export interface PaginationRootProps extends Omit<ChakraPagination.RootProps, 'type'> {
  size?: ButtonProps['size'];
  variant?: PaginationVariant;
  getHref?: (page: number) => string;
  getChildLink?: (page: number, render: React.ReactNode) => React.ReactNode;
}

const paginationVariantMap: Record<PaginationVariant, ButtonVariantMap> = {
  outline: { default: 'ghost', ellipsis: 'plain', current: 'outline' },
  solid: { default: 'outline', ellipsis: 'outline', current: 'solid' },
  subtle: { default: 'ghost', ellipsis: 'plain', current: 'subtle' },
};

export const PaginationRoot = React.forwardRef<HTMLDivElement, PaginationRootProps>(
  function PaginationRoot(props, ref) {
    const { size = 'sm', variant = 'outline', getHref, getChildLink, ...rest } = props;
    return (
      <RootPropsProvider
        value={{ size, variantMap: paginationVariantMap[variant], getHref, getChildLink }}
      >
        <ChakraPagination.Root
          ref={ref}
          type={getHref || getChildLink ? 'link' : 'button'}
          {...rest}
        />
      </RootPropsProvider>
    );
  },
);

export const PaginationEllipsis = React.forwardRef<HTMLDivElement, ChakraPagination.EllipsisProps>(
  function PaginationEllipsis(props, ref) {
    const { size, variantMap: activeVariantMap } = useRootProps();
    return (
      <ChakraPagination.Ellipsis ref={ref} {...props} asChild>
        <Button as="span" variant={activeVariantMap.ellipsis} size={size}>
          <HiMiniEllipsisHorizontal />
        </Button>
      </ChakraPagination.Ellipsis>
    );
  },
);

export const PaginationItem = React.forwardRef<HTMLButtonElement, ChakraPagination.ItemProps>(
  function PaginationItem(props, ref) {
    const { page } = usePaginationContext();
    const { size, variantMap: activeVariantMap, getHref, getChildLink } = useRootProps();

    const current = page === props.value;
    const variant = current ? activeVariantMap.current : activeVariantMap.default;

    if (getHref) {
      return (
        <LinkButton href={getHref(props.value)} variant={variant} size={size}>
          {props.value}
        </LinkButton>
      );
    }

    if (getChildLink) {
      return (
        <LinkButton asChild variant={variant} size={size}>
          {getChildLink(props.value, props.value)}
        </LinkButton>
      );
    }

    return (
      <ChakraPagination.Item ref={ref} {...props} asChild>
        <Button variant={variant} size={size}>
          {props.value}
        </Button>
      </ChakraPagination.Item>
    );
  },
);

export const PaginationPrevTrigger = React.forwardRef<
  HTMLButtonElement,
  ChakraPagination.PrevTriggerProps
>(function PaginationPrevTrigger(props, ref) {
  const { size, variantMap: activeVariantMap, getHref, getChildLink } = useRootProps();
  const { previousPage } = usePaginationContext();

  if (getHref) {
    return (
      <LinkButton
        href={previousPage != null ? getHref(previousPage) : undefined}
        variant={activeVariantMap.default}
        size={size}
      >
        <HiChevronLeft />
      </LinkButton>
    );
  }

  if (getChildLink && previousPage != null) {
    return (
      <LinkButton asChild variant={activeVariantMap.default} size={size}>
        {getChildLink(previousPage, <HiChevronLeft />)}
      </LinkButton>
    );
  }
  if (getChildLink && previousPage == null) {
    return (
      <LinkButton href={undefined} variant={activeVariantMap.default} size={size}>
        <HiChevronLeft />
      </LinkButton>
    );
  }

  return (
    <ChakraPagination.PrevTrigger ref={ref} asChild {...props}>
      <IconButton variant={activeVariantMap.default} size={size}>
        <HiChevronLeft />
      </IconButton>
    </ChakraPagination.PrevTrigger>
  );
});

export const PaginationNextTrigger = React.forwardRef<
  HTMLButtonElement,
  ChakraPagination.NextTriggerProps
>(function PaginationNextTrigger(props, ref) {
  const { size, variantMap: activeVariantMap, getHref, getChildLink } = useRootProps();
  const { nextPage } = usePaginationContext();

  if (getHref) {
    return (
      <LinkButton
        href={nextPage != null ? getHref(nextPage) : undefined}
        variant={activeVariantMap.default}
        size={size}
      >
        <HiChevronRight />
      </LinkButton>
    );
  }

  if (getChildLink && nextPage != null) {
    return (
      <LinkButton asChild variant={activeVariantMap.default} size={size}>
        {getChildLink(nextPage, <HiChevronRight />)}
      </LinkButton>
    );
  }
  if (getChildLink && nextPage == null) {
    return (
      <LinkButton href={undefined} variant={activeVariantMap.default} size={size}>
        <HiChevronRight />
      </LinkButton>
    );
  }

  return (
    <ChakraPagination.NextTrigger ref={ref} asChild {...props}>
      <IconButton variant={activeVariantMap.default} size={size}>
        <HiChevronRight />
      </IconButton>
    </ChakraPagination.NextTrigger>
  );
});

export const PaginationItems = (props: React.HTMLAttributes<HTMLElement>) => {
  return (
    <ChakraPagination.Context>
      {({ pages }) =>
        pages.map((page, index) => {
          return page.type === 'ellipsis' ? (
            <PaginationEllipsis key={index} index={index} {...props} />
          ) : (
            <PaginationItem key={index} type="page" value={page.value} {...props} />
          );
        })
      }
    </ChakraPagination.Context>
  );
};

interface PageTextProps extends TextProps {
  format?: 'short' | 'compact' | 'long';
}

export const PaginationPageText = React.forwardRef<HTMLParagraphElement, PageTextProps>(
  function PaginationPageText(props, ref) {
    const { format = 'compact', ...rest } = props;
    const { page, totalPages, pageRange, count } = usePaginationContext();
    const content = React.useMemo(() => {
      if (format === 'short') return `${page} / ${totalPages}`;
      if (format === 'compact') return `${page} of ${totalPages}`;
      return `${pageRange.start + 1} - ${Math.min(pageRange.end, count)} of ${count}`;
    }, [format, page, totalPages, pageRange, count]);

    return (
      <Text fontWeight="medium" ref={ref} {...rest}>
        {content}
      </Text>
    );
  },
);
