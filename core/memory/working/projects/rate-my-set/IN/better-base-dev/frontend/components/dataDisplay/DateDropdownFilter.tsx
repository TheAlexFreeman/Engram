import { useCallback, useMemo, useState } from 'react';

import {
  Icon,
  MenuRootProps,
  PopoverArrow,
  PopoverBody,
  PopoverContent,
  PopoverTrigger,
} from '@chakra-ui/react';
import ChevronDownIcon from '@heroicons/react/24/solid/esm/ChevronDownIcon';
import FunnelIcon from '@heroicons/react/24/solid/esm/FunnelIcon';

import { Button } from '@/components/ui/button';

import { MenuContent, MenuRadioItem, MenuRadioItemGroup, MenuRoot, MenuTrigger } from '../ui/menu';
import { PopoverRoot } from '../ui/popover';
import DateRangeFilter from './DateRangeFilter';

type DateDropdownFilterLabelMapping = {
  readonly all: 'All days';
  readonly today: 'Today';
  readonly yesterday: 'Yesterday';
  readonly last3d: 'Last 3 days';
  readonly last7d: 'Last 7 days';
  readonly last30d: 'Last 30 days';
  readonly thisMonth: 'This month';
  readonly lastMonth: 'Last month';
  readonly custom: 'Custom date range';
};

export type DashboardDateDropdownFilterValues = {
  optionValue:
    | keyof Pick<DateDropdownFilterLabelMapping, 'last7d' | 'last30d' | 'custom'>
    | ''
    | null
    | undefined;
  customStartDate: string | null | undefined;
  customEndDate: string | null | undefined;
};

export type DateDropdownFilterValues = {
  optionValue: keyof DateDropdownFilterLabelMapping | '' | null | undefined;
  customStartDate: string | null | undefined;
  customEndDate: string | null | undefined;
};

export type DateDropdownFilterProps = {
  optionValue?: keyof typeof labelMapping | '' | null | undefined;
  customStartDate?: string | null | undefined;
  customEndDate?: string | null | undefined;
  updateValues?: (updateData: DateDropdownFilterValues) => void;
  menuButton?: React.ReactNode;
  optionKeys?: (keyof DateDropdownFilterLabelMapping)[];
} & Partial<MenuRootProps>;

export default function DateDropdownFilter({
  optionValue,
  customStartDate,
  customEndDate,
  updateValues,
  menuButton,
  optionKeys,
  ...menuProps
}: DateDropdownFilterProps) {
  const initiallySelected: keyof typeof labelMapping =
    !optionValue && (customStartDate || customEndDate) ? 'custom' : optionValue || 'all';

  const [values, setValues] = useState<DateDropdownFilterValues>({
    optionValue: initiallySelected,
    customStartDate: initiallySelected === 'custom' ? customStartDate || undefined : undefined,
    customEndDate: initiallySelected === 'custom' ? customEndDate || undefined : undefined,
  });

  const selected = useMemo(() => values.optionValue || 'all', [values.optionValue]);
  const selectedLabel = useMemo(() => labelMapping[selected], [selected]);
  const defaultValue = useMemo(() => (selected === 'custom' ? undefined : selected), [selected]);

  const customIsOpen = useMemo(() => selected === 'custom', [selected]);
  // Store these in memory so that, if the user clicks away from the custom option but
  // then clicks back to it in the same browsing session, the previous custom date range
  // values are restored.
  const [lastCustomStart, setLastCustomStart] = useState(customStartDate);
  const [lastCustomEnd, setLastCustomEnd] = useState(customEndDate);

  const onClose = useCallback(() => {
    if (updateValues) {
      updateValues(values);
    }
  }, [updateValues, values]);

  const onChange = useCallback(
    (nextOptionValue: unknown) => {
      let newValues: DateDropdownFilterValues;
      if (nextOptionValue === 'custom') {
        newValues = {
          optionValue: nextOptionValue,
          customStartDate: values.customStartDate || undefined,
          customEndDate: values.customEndDate || undefined,
        };
        setValues(newValues);
      } else {
        newValues = {
          optionValue:
            (nextOptionValue as keyof DateDropdownFilterLabelMapping | '' | null) || undefined,
          customStartDate: undefined,
          customEndDate: undefined,
        };
        setValues(newValues);
        updateValues?.(newValues);
      }
    },
    [values.customStartDate, values.customEndDate, updateValues],
  );

  const onCustomOpened = useCallback(() => {
    const newValues: DateDropdownFilterValues = {
      optionValue: 'custom',
      customStartDate: values.customStartDate || lastCustomStart || undefined,
      customEndDate: values.customEndDate || lastCustomEnd || undefined,
    };
    setValues(newValues);
    updateValues?.(newValues);
  }, [values.customStartDate, values.customEndDate, lastCustomStart, lastCustomEnd, updateValues]);

  const onCustomChange = useCallback(
    ({ start, end }: { start: string | null | undefined; end: string | null | undefined }) => {
      const newValues: DateDropdownFilterValues = {
        optionValue: 'custom',
        customStartDate: start || undefined,
        customEndDate: end || undefined,
      };

      if ((start && start[0] === '0') || (end && end[0] === '0')) {
        return;
      }

      setValues(newValues);
      updateValues?.(newValues);
      setLastCustomStart(start);
      setLastCustomEnd(end);
    },
    [updateValues],
  );

  const presetKeys = useMemo(
    () => optionKeys || (Object.keys(labelMapping) as (keyof DateDropdownFilterLabelMapping)[]),
    [optionKeys],
  );
  const options = useMemo(
    () =>
      presetKeys.map((key) => ({
        key,
        value: key,
        label: labelMapping[key],
        isChecked: key === selected,
      })),
    [presetKeys, selected],
  );

  return (
    <MenuRoot closeOnSelect={false} onOpenChange={(e) => !e.open && onClose()} {...menuProps}>
      {menuButton || (
        <MenuTrigger asChild>
          <Button
            variant="ghost"
            bgColor="bg.level1"
            color="text.lighter"
            _hover={{
              bgColor: 'bg.level2',
              color: 'text.light',
            }}
            _active={{
              bgColor: 'bg.level2',
              color: 'text.light',
            }}
          >
            <Icon as={FunnelIcon} />
            {selectedLabel}
            <Icon as={ChevronDownIcon} />
          </Button>
        </MenuTrigger>
      )}
      <MenuContent minWidth="240px">
        <MenuRadioItemGroup
          defaultValue={defaultValue}
          onChange={onChange}
          value={selected}
          title="Filter by time"
        >
          {options.map(
            ({ key, value, label: optionLabel }) =>
              key !== 'custom' && (
                <MenuRadioItem key={key} value={value}>
                  {optionLabel}
                </MenuRadioItem>
              ),
          )}
        </MenuRadioItemGroup>
        <PopoverRoot open={customIsOpen} onOpenChange={(e) => e.open && onCustomOpened()}>
          <PopoverTrigger>
            <Button
              variant="solid"
              bgColor="bg.level1"
              color="text.main"
              _hover={{
                bgColor: 'bg.level2',
                color: 'text.main',
              }}
              _active={{
                bgColor: 'bg.level2',
                color: 'text.main',
              }}
              mt="2"
              mx="2"
              borderRadius="2xl"
              width="calc(100% - var(--chakra-spacing-4))"
            >
              Custom date range
            </Button>
          </PopoverTrigger>
          <PopoverContent w="fit-content">
            <PopoverArrow />

            <PopoverBody>
              <DateRangeFilter
                start={values.customStartDate}
                end={values.customEndDate}
                onUpdate={onCustomChange}
              />
            </PopoverBody>
          </PopoverContent>
        </PopoverRoot>
      </MenuContent>
    </MenuRoot>
  );
}

const labelMapping: DateDropdownFilterLabelMapping = {
  all: 'All days',
  today: 'Today',
  yesterday: 'Yesterday',
  last3d: 'Last 3 days',
  last7d: 'Last 7 days',
  last30d: 'Last 30 days',
  thisMonth: 'This month',
  lastMonth: 'Last month',
  custom: 'Custom date range',
};
