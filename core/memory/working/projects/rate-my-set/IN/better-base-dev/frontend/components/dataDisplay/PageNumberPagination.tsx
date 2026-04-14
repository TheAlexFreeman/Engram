import { useCallback, useMemo } from 'react';

import { Box, HStack, Icon, IconButton, StackProps } from '@chakra-ui/react';
import ChevronDownIcon from '@heroicons/react/20/solid/esm/ChevronDownIcon';
import ChevronLeftIcon from '@heroicons/react/20/solid/esm/ChevronLeftIcon';
import ChevronRightIcon from '@heroicons/react/20/solid/esm/ChevronRightIcon';

import { Button } from '@/components/ui/button';

import { MenuContent, MenuRadioItem, MenuRadioItemGroup, MenuRoot, MenuTrigger } from '../ui/menu';

type PageNumberPaginationProps = {
  pagination: {
    pageNumber: number;
    lastPageNumber: number;
    pageSize: number;
    hasPrevious: boolean;
    hasNext: boolean;
    nearbyPageNumbers: (number | '...' | '…')[];
    totalNumRecords: number;
  };
  updateValues: (updateData: { pageNumber: number; pageSize: number }) => void;
} & Partial<StackProps>;

export default function PageNumberPagination({
  pagination: { pageNumber, pageSize, nearbyPageNumbers, lastPageNumber },
  updateValues,
  ...stackProps
}: PageNumberPaginationProps) {
  const availablePageSizes = useMemo(() => [10, 25, 50, 100], []);
  const pageNumberChoices = useMemo(
    () =>
      nearbyPageNumbers.map((n, i) => {
        const isEllipsis = n === '...' || n === '…';
        const isChecked = !isEllipsis && n == pageNumber;
        const isDisabled = isEllipsis;
        const key = isEllipsis ? `ellipsis-${i}` : n.toString();
        return {
          key,
          value: n.toString(),
          label: isEllipsis ? '…' : `Page ${n.toString()}`,
          isChecked,
          isDisabled,
          isEllipsis,
        };
      }),
    [pageNumber, nearbyPageNumbers],
  );

  const updatePageNumber = useCallback(
    (newPageNumber: number) => {
      updateValues({ pageNumber: newPageNumber, pageSize });
    },
    [updateValues, pageSize],
  );

  const updatePageSize = useCallback(
    (newPageSize: number) => {
      updateValues({ pageNumber, pageSize: newPageSize });
    },
    [updateValues, pageNumber],
  );

  const onPageNumberChanged = useCallback(
    (newPageNumber: string | string[]) => {
      updatePageNumber(Number(newPageNumber as string));
    },
    [updatePageNumber],
  );

  const onPageSizeChanged = useCallback(
    (newPageSize: string | string[]) => {
      updatePageSize(Number(newPageSize as string));
    },
    [updatePageSize],
  );

  const showPreviousPage = useMemo(() => pageNumber > 1, [pageNumber]);

  const showNextPage = useMemo(
    () => !!lastPageNumber && pageNumber < lastPageNumber,
    [pageNumber, lastPageNumber],
  );

  const onPreviousPageClicked = useCallback(() => {
    updatePageNumber(pageNumber - 1);
  }, [updatePageNumber, pageNumber]);

  const onNextPageClicked = useCallback(() => {
    updatePageNumber(pageNumber + 1);
  }, [updatePageNumber, pageNumber]);

  return (
    <HStack justifyContent="space-between" {...stackProps}>
      <MenuRoot closeOnSelect={true}>
        <MenuTrigger asChild>
          <Button
            h="7"
            pl="3"
            pr="2"
            variant="ghost"
            textStyle="buttonM"
            color="primary.text.main"
            bgColor="primary.bg.lighter"
            _hover={{
              bgColor: 'primary.bg.light',
            }}
            _active={{
              bgColor: 'primary.bg.light',
            }}
          >
            <Box textStyle="buttonM">{pageSize} items per row</Box>
            <Icon as={ChevronDownIcon} />
          </Button>
        </MenuTrigger>
        <MenuContent minWidth="240px">
          <MenuRadioItemGroup
            defaultValue={pageSize.toString()}
            onValueChange={(e) => onPageSizeChanged(e.value)}
            value={pageSize.toString()}
            title=""
            textStyle="h6"
            color="text.light"
          >
            {availablePageSizes.map((availableSize: number) => (
              <MenuRadioItem
                key={availableSize}
                value={availableSize.toString()}
                textStyle="buttonM"
                color="text.main"
                borderRadius="full"
                _hover={{
                  bgColor: 'primary.bg.light',
                }}
              >
                {availableSize} items
              </MenuRadioItem>
            ))}
          </MenuRadioItemGroup>
        </MenuContent>
      </MenuRoot>
      <HStack>
        <IconButton
          disabled={!showPreviousPage}
          onClick={onPreviousPageClicked}
          h="7"
          aria-label="Previous page"
          color="primary.text.main"
          bgColor="primary.bg.lighter"
          _hover={{
            bgColor: 'primary.bg.light',
          }}
          _active={{
            bgColor: 'primary.bg.light',
          }}
        >
          <Icon as={ChevronLeftIcon} />
        </IconButton>
        <IconButton
          disabled={!showNextPage}
          onClick={onNextPageClicked}
          h="7"
          aria-label="Next page"
          color="primary.text.main"
          bgColor="primary.bg.lighter"
          _hover={{
            bgColor: 'primary.bg.light',
          }}
          _active={{
            bgColor: 'primary.bg.light',
          }}
        >
          <Icon as={ChevronRightIcon} />
        </IconButton>
        <MenuRoot closeOnSelect={true}>
          <MenuTrigger asChild>
            <Button
              h="7"
              pl="3"
              pr="2"
              variant="ghost"
              textStyle="buttonM"
              color="primary.text.main"
              bgColor="primary.bg.lighter"
              _hover={{
                bgColor: 'primary.bg.light',
              }}
              _active={{
                bgColor: 'primary.bg.light',
              }}
              _disabled={{
                bgColor: 'primary.bg.lighter',
              }}
            >
              <Box textStyle="buttonM">Page {pageNumber}</Box>
              <Icon as={ChevronDownIcon} />
            </Button>
          </MenuTrigger>
          <MenuContent minWidth="240px">
            <MenuRadioItemGroup
              defaultValue={pageNumber.toString()}
              onValueChange={(e) => onPageNumberChanged(e.value)}
              value={pageNumber.toString()}
              title=""
              textStyle="h6"
              color="text.light"
            >
              {pageNumberChoices.map(({ key, value, label, isDisabled }) => (
                <MenuRadioItem
                  key={key}
                  value={value}
                  disabled={isDisabled}
                  textStyle="buttonM"
                  color="text.main"
                  _hover={{
                    bgColor: 'primary.bg.light',
                  }}
                >
                  {label}
                </MenuRadioItem>
              ))}
            </MenuRadioItemGroup>
          </MenuContent>
        </MenuRoot>
        <Box textStyle="buttonM" color="primary.text.main">
          of {lastPageNumber} {lastPageNumber == 1 ? 'page' : 'pages'}
        </Box>
      </HStack>
    </HStack>
  );
}
