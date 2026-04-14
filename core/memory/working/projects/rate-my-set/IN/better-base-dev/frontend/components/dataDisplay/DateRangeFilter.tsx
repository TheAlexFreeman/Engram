import { useCallback, useMemo } from 'react';

import { Field, HStack, Icon } from '@chakra-ui/react';
import CalendarIcon from '@heroicons/react/20/solid/CalendarIcon';
import { SingleDatepicker } from 'chakra-dayzed-datepicker';
import { format, parse } from 'date-fns';

import { toaster } from '../ui/toaster';

export type DateRangeFilterProps = {
  start?: string | null;
  end?: string | null;
  onUpdate: ({
    start,
    end,
  }: {
    start: string | null | undefined;
    end: string | null | undefined;
  }) => void;
};

export default function DateRangeFilter({ start, end, onUpdate }: DateRangeFilterProps) {
  const startDate = useMemo(
    () => (start ? parse(start, 'yyyy-MM-dd', new Date()) : undefined),
    [start],
  );
  const endDate = useMemo(() => (end ? parse(end, 'yyyy-MM-dd', new Date()) : undefined), [end]);

  const setNewStart = useCallback(
    (newStart: Date | undefined) => {
      if (!isValidDate(newStart)) {
        toaster.create({
          title: 'Invalid date format. Please use the format mm/dd/yyyy.',
          type: 'error',
          duration: 7000,
          meta: { closable: true },
        });
        return;
      }

      const formattedEnd = endDate ? format(endDate, 'yyyy-MM-dd') : undefined;

      if (newStart) {
        const formattedStart = format(newStart, 'yyyy-MM-dd');

        // Assume this was an incomplete date that was parsed automatically.
        if (formattedStart.startsWith('0')) return;

        // Swap start and end if start is after end.
        if (endDate && newStart > endDate) {
          onUpdate({ start: formattedEnd, end: formattedStart });
          toaster.create({
            title: 'We switched your date range so that your start date is before your end date.',
            type: 'info',
            duration: 7000,
            meta: { closable: true },
          });
        } else {
          onUpdate({ start: formattedStart, end: formattedEnd });
        }
      } else {
        onUpdate({ start: newStart, end: formattedEnd });
      }
    },
    [endDate, onUpdate],
  );

  const setNewEnd = useCallback(
    (newEnd: Date | undefined) => {
      if (!isValidDate(newEnd)) {
        toaster.create({
          title: 'Invalid date format. Please use the format mm/dd/yyyy.',
          type: 'error',
          duration: 7000,
          meta: { closable: true },
        });
        return;
      }

      const formattedStart = startDate ? format(startDate, 'yyyy-MM-dd') : undefined;

      if (newEnd) {
        const formattedEnd = format(newEnd, 'yyyy-MM-dd');
        // Assume this was an incomplete date that was parsed automatically.
        if (formattedEnd.startsWith('0')) return;

        // Swap start and end if start is after end.
        if (startDate && newEnd < startDate) {
          onUpdate({ start: formattedEnd, end: formattedStart });
          toaster.create({
            title: 'We switched your date range so that your start date is before your end date.',
            type: 'info',
            duration: 7000,
            meta: { closable: true },
          });
        } else {
          onUpdate({ start: formattedStart, end: formattedEnd });
        }
      } else {
        onUpdate({ start: formattedStart, end: newEnd });
      }
    },
    [onUpdate, startDate],
  );

  const {
    propsConfigs: { inputProps, ...otherPropsConfigs },
    ...otherDatepickerProps
  } = useMemo(
    () => ({
      configs: {
        dateFormat: 'MM/dd/yyyy',
        dayNames: ['Su', 'M', 'T', 'W', 'Th', 'F', 'Sa'],
        firstDayOfWeek: 1 as const,
      },

      propsConfigs: {
        inputProps: { placeholder: 'mm/dd/yyyy' },
        dayOfMonthBtnProps: {
          defaultBtnProps: {
            h: '10',
            w: '10',
            borderRadius: 'full',
            color: 'text.main',
            _hover: { bg: 'primary.bg.light' },
          },
          todayBtnProps: {
            h: '10',
            w: '10',
            borderRadius: 'full',
            borderWidth: '2px',
            borderStyle: 'solid',
            borderColor: 'primary.bg.light',
            bg: 'primary.bg.lighter',
            color: 'text.main',
            _hover: { bg: 'primary.bg.light' },
          },
          selectedBtnProps: {
            h: '10',
            w: '10',
            borderRadius: 'full',
            bg: 'primary.bg.main',
            color: 'text.inverse',
            _hover: { bg: 'primary.bg.contrast' },
          },
        },
        weekdayLabelProps: {
          color: 'primary.text.light',
        },
      },
      triggerVariant: 'input' as const,
      triggerIcon: <Icon as={CalendarIcon} />,
    }),
    [],
  );

  return (
    <HStack gap={2}>
      <Field.Root>
        <Field.Label>Start Date</Field.Label>
        <SingleDatepicker
          name="start"
          date={startDate}
          onDateChange={setNewStart}
          propsConfigs={{
            inputProps: {
              ...inputProps,
            },
            ...otherPropsConfigs,
          }}
          {...otherDatepickerProps}
        />{' '}
      </Field.Root>
      <Field.Root>
        <Field.Label>End Date</Field.Label>
        <SingleDatepicker
          name="end"
          date={endDate}
          onDateChange={setNewEnd}
          propsConfigs={{
            inputProps: {
              ...inputProps,
            },
            ...otherPropsConfigs,
          }}
          {...otherDatepickerProps}
        />
      </Field.Root>
    </HStack>
  );
}

// Thanks to https://stackoverflow.com/a/44198641
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isValidDate(date: any) {
  return date && Object.prototype.toString.call(date) === '[object Date]' && !isNaN(date);
}
