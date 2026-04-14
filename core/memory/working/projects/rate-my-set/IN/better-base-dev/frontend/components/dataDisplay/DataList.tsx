import { useCallback, useMemo } from 'react';

import {
  Box,
  HStack,
  Table,
  type TableBodyProps,
  type TableCaptionProps,
  type TableCellProps,
  type TableColumnHeaderProps,
  type TableFooterProps,
  type TableHeaderProps,
  type TableRootProps,
  type TableRowProps,
  type TableScrollAreaProps,
  Text,
  VStack,
} from '@chakra-ui/react';
import lodashGet from 'lodash-es/get';

import NoDataIllustration from '@/assets/illustrations/NoDataIllustration';
import { textStyles } from '@/theme/text-styles';
import { type NestedPaths } from '@/utils/types/objectNestedKeyPaths';

import { Checkbox } from '../ui/checkbox';

const {
  Root: TableRoot,
  Body: TableBody,
  Header: TableHeader,
  Footer: TableFooter,
  Row: TableRow,
  Cell: TableCell,
  ColumnHeader: TableColumnHeader,
  Caption: TableCaption,
  ScrollArea: TableScrollArea,
} = Table;

const _deepGet = lodashGet;

function deepGet<T extends object>(obj: T, path: FieldType<T>) {
  if (path.includes('.')) {
    return _deepGet(obj, path);
  }
  return obj[path as keyof T];
}

export type Row<T extends object> = T;

export type FieldType<T extends object> = (keyof T & string) | (NestedPaths<T> & string);

export type ColumnDefRegular<T extends object> = {
  columnType?: undefined;
  field: FieldType<T>;
  label: string;
  getFieldValue?: (row: Row<T>) => React.ReactNode;
  renderHeader?: (columnDef: ColumnDef<T>) => React.ReactNode;
  renderCell?: (row: Row<T>) => React.ReactNode;
  renderFooter?: (columnDef: ColumnDef<T>) => React.ReactNode;
};

type _ColumnDefCustomBase<T extends object> = {
  columnType: 'custom';
  key: string;
  label?: string;
  renderHeader?: (columnDef: ColumnDef<T>) => React.ReactNode;
  renderFooter?: (columnDef: ColumnDef<T>) => React.ReactNode;
};

type _ColumnDefCustomWithGetFieldValue<T extends object> = _ColumnDefCustomBase<T> & {
  getFieldValue: (row: Row<T>) => React.ReactNode;
  renderCell?: (row: Row<T>) => React.ReactNode;
};

type _ColumnDefCustomWithRenderCell<T extends object> = _ColumnDefCustomBase<T> & {
  getFieldValue?: (row: Row<T>) => React.ReactNode;
  renderCell: (row: Row<T>) => React.ReactNode;
};

export type ColumnDefCustom<T extends object> =
  | _ColumnDefCustomWithGetFieldValue<T>
  | _ColumnDefCustomWithRenderCell<T>;

export type ColumnDef<T extends object> = ColumnDefRegular<T> | ColumnDefCustom<T>;

export type DataListSelectConfig<T extends object> = {
  selectedRows: Row<T>[];
  onRowSelected: (row: Row<T>) => void;
  exclude?: (row: Row<T>) => boolean;
};

export type DataListConfig<T extends object> = {
  idField?: FieldType<T>;
  caption?: React.ReactNode;
  includeFooter?: boolean;
  isFiltered?: boolean;
};

export type DataListSlotProps<T extends object> = {
  table?: TableRootProps;
  thead?: TableHeaderProps;
  tbody?: TableBodyProps;
  tfoot?: TableFooterProps;
  tr?:
    | TableRowProps
    | ((
        info:
          | { position: 'head' | 'foot'; columnDefs: ColumnDef<T>[] }
          | { position: 'body'; columnDefs: ColumnDef<T>[]; row: Row<T> },
      ) => TableRowProps);
  th?:
    | TableColumnHeaderProps
    | ((info: { position: 'head' | 'foot'; columnDef: ColumnDef<T> }) => TableColumnHeaderProps);
  td?:
    | TableCellProps
    | ((info: {
        position: 'body';
        columnDef: ColumnDef<T>;
        row: Row<T>;
        fieldValue: React.ReactNode;
      }) => TableCellProps);
  tableCaption?: TableCaptionProps;
  tableContainer?: TableScrollAreaProps;
};

export type DataListProps<T extends object> = {
  columnDefs: ColumnDef<T>[];
  rows: Row<T>[];
  select?: DataListSelectConfig<T>;
  config?: DataListConfig<T>;
  slotProps?: DataListSlotProps<T>;
};

type BodyCellProps<T extends object> = {
  row: Row<T>;
  columnDef: ColumnDef<T>;
  slotProps: DataListProps<T>['slotProps'];
  select?: {
    hasCheckbox: boolean;
    isSelectable: boolean;
    isSelected: boolean;
    onSelect: (r: Row<T>) => void;
  };
};

// Non-function defaults only (function variants are handled at call sites).
const slotPropsDefaults: {
  table?: TableRootProps;
  thead?: TableHeaderProps;
  tbody?: TableBodyProps;
  tfoot?: TableFooterProps;
  th?: TableColumnHeaderProps;
  tableCaption?: TableCaptionProps;
  tableContainer?: TableScrollAreaProps;
} = {
  table: {
    variant: 'line',
  },
  thead: {
    borderBottomWidth: '2px',
    borderBottomColor: 'border.emphasized',
  },
  th: {
    ...textStyles.h5,
    textTransform: 'none',
    letterSpacing: 'normal',
    pb: 0,
  },
};

export default function DataList<T extends object>({
  columnDefs,
  rows,
  select,
  config = {},
  slotProps = {},
}: DataListProps<T>) {
  const idField = config?.idField || ('id' as FieldType<T>);

  const caption = config?.caption;

  const includeFooter = config?.includeFooter ?? false;

  const isSelected = useCallback((row: Row<T>) => !!select?.selectedRows?.includes(row), [select]);

  const isSelectable = useCallback(
    (row: Row<T>) => !!select && (!select?.exclude || !select.exclude(row)),
    [select],
  );

  const rowProps = useCallback(
    (row: Row<T>) => ({
      row: row,
      columnDefs: columnDefs,
      slotProps: slotProps,
      select: select
        ? {
            isSelectable: isSelectable(row),
            isSelected: isSelected(row),
            onSelect: select.onRowSelected,
          }
        : undefined,
    }),
    [columnDefs, select, isSelectable, isSelected, slotProps],
  );

  const noDataText = useMemo(() => {
    if (config.isFiltered) {
      return "We don't have data that matches your request. Please try adjusting your filters or search terms.";
    }
    return "We don't have data for this table yet.";
  }, [config.isFiltered]);

  return (
    <>
      <TableScrollArea
        {...{
          ...slotPropsDefaults?.tableContainer,
          ...slotProps?.tableContainer,
        }}
      >
        <TableRoot
          {...{
            ...slotPropsDefaults?.table,
            ...slotProps?.table,
          }}
        >
          {caption && (
            <TableCaption
              {...{
                ...slotPropsDefaults?.tableCaption,
                ...slotProps?.tableCaption,
              }}
            >
              {caption}
            </TableCaption>
          )}
          <TableHeader
            {...{
              ...slotPropsDefaults?.thead,
              ...slotProps?.thead,
            }}
          >
            <HeaderRow columnDefs={columnDefs} slotProps={slotProps} />
          </TableHeader>
          <TableBody
            {...{
              ...slotPropsDefaults?.tbody,
              ...slotProps?.tbody,
            }}
          >
            {rows.map((row) => (
              <BodyRow key={deepGet(row, idField) as React.Key} {...rowProps(row)} />
            ))}
          </TableBody>
          {includeFooter && (
            <TableFooter
              {...{
                ...slotPropsDefaults?.tfoot,
                ...slotProps?.tfoot,
              }}
            >
              <FooterRow columnDefs={columnDefs} slotProps={slotProps} />
            </TableFooter>
          )}
        </TableRoot>
      </TableScrollArea>
      {rows.length === 0 && (
        <VStack bgColor="bg.level1" py="9">
          <NoDataIllustration />
          <Text color="text.light">{noDataText}</Text>
        </VStack>
      )}
    </>
  );
}

function HeaderRow<T extends object>({
  columnDefs,
  slotProps,
}: {
  columnDefs: ColumnDef<T>[];
  slotProps: DataListProps<T>['slotProps'];
}) {
  const initialProps = slotProps?.tr;

  let props: TableRowProps | undefined;
  if (typeof initialProps === 'function') {
    props = initialProps({ position: 'head', columnDefs });
  } else {
    props = initialProps;
  }
  return (
    <TableRow {...props}>
      {columnDefs.map((columnDef) => (
        <HeaderCell
          key={columnDef.columnType === 'custom' ? columnDef.key : columnDef.field}
          columnDef={columnDef}
          slotProps={slotProps}
        />
      ))}
    </TableRow>
  );
}

function FooterRow<T extends object>({
  columnDefs,
  slotProps,
}: {
  columnDefs: ColumnDef<T>[];
  slotProps: DataListProps<T>['slotProps'];
}) {
  const initialProps = slotProps?.tr;

  let props: TableRowProps | undefined;
  if (typeof initialProps === 'function') {
    props = initialProps({ position: 'foot', columnDefs });
  } else {
    props = initialProps;
  }
  return (
    <TableRow {...props}>
      {columnDefs.map((columnDef) => (
        <FooterCell
          key={columnDef.columnType === 'custom' ? columnDef.key : columnDef.field}
          columnDef={columnDef}
          slotProps={slotProps}
        />
      ))}
    </TableRow>
  );
}

function HeaderCell<T extends object>({
  columnDef,
  slotProps,
}: {
  columnDef: ColumnDef<T>;
  slotProps: DataListProps<T>['slotProps'];
}) {
  const initialProps = slotProps?.th;

  let props: TableColumnHeaderProps | undefined;
  if (typeof initialProps === 'function') {
    props = initialProps({ position: 'head', columnDef });
  } else {
    props = initialProps;
  }
  props = { ...slotPropsDefaults?.th, ...props };

  let inside: React.ReactNode;
  if (columnDef.renderHeader != null) {
    inside = columnDef.renderHeader(columnDef);
  } else {
    inside = <Text textStyle="h6">{columnDef.label}</Text>;
  }

  return <TableColumnHeader {...props}>{inside}</TableColumnHeader>;
}

function FooterCell<T extends object>({
  columnDef,
  slotProps,
}: {
  columnDef: ColumnDef<T>;
  slotProps: DataListProps<T>['slotProps'];
}) {
  const initialProps = slotProps?.th;
  let props: TableColumnHeaderProps | undefined;
  if (typeof initialProps === 'function') {
    props = initialProps({ position: 'foot', columnDef });
  } else {
    props = initialProps;
  }
  props = { ...slotPropsDefaults?.th, ...props };

  let inside: React.ReactNode;
  if (columnDef.renderFooter != null) {
    inside = columnDef.renderFooter(columnDef);
  } else {
    inside = columnDef.label;
  }

  return <TableColumnHeader {...props}>{inside}</TableColumnHeader>;
}

function BodyRow<T extends object>({
  row,
  columnDefs,
  select,
  slotProps,
}: {
  row: Row<T>;
  select?: {
    isSelectable: boolean;
    isSelected: boolean;
    onSelect: (row: Row<T>) => void;
  };
  columnDefs: ColumnDef<T>[];
  slotProps: DataListProps<T>['slotProps'];
}) {
  const initialProps = slotProps?.tr;
  let props: TableRowProps | undefined;
  if (typeof initialProps === 'function') {
    props = initialProps({ position: 'body', columnDefs, row });
  } else {
    props = initialProps;
  }

  if (select?.isSelectable) {
    props = {
      ...props,
      _hover: { bgColor: 'primary.bg.lighter' },
    };

    if (select?.isSelected) {
      props = {
        ...props,
        bgColor: 'primary.bg.light',
      };
    }
  }

  return (
    <TableRow {...props}>
      {columnDefs.map((columnDef, index) => {
        const cellProps: BodyCellProps<T> = { row, columnDef, slotProps };
        if (select) {
          cellProps.select = {
            ...select,
            hasCheckbox: index === 0,
          };
        }
        return (
          <BodyCell
            key={columnDef.columnType === 'custom' ? columnDef.key : columnDef.field}
            {...cellProps}
          />
        );
      })}
    </TableRow>
  );
}

function BodyCell<T extends object>({ row, columnDef, select, slotProps }: BodyCellProps<T>) {
  let fieldValue: React.ReactNode;
  if (columnDef.getFieldValue != null) {
    fieldValue = columnDef.getFieldValue(row);
  } else if (columnDef.renderCell != null) {
    fieldValue = columnDef.renderCell(row);
  } else {
    fieldValue = deepGet(
      row,
      (columnDef as Exclude<ColumnDef<T>, ColumnDefCustom<T>>).field,
    ) as React.ReactNode;
  }

  const initialProps = slotProps?.td;
  let props: TableCellProps | undefined;
  if (typeof initialProps === 'function') {
    props = initialProps({ position: 'body', columnDef, row, fieldValue });
  } else {
    props = initialProps;
  }

  const selectableProps = useMemo(
    () => (select?.isSelectable ? { cursor: 'pointer', onClick: () => select.onSelect(row) } : {}),
    [row, select],
  );

  let inside: React.ReactNode;
  if (columnDef.renderCell != null) {
    inside = columnDef.renderCell(row);
  } else {
    inside = fieldValue;
  }

  if (select?.hasCheckbox) {
    const { isSelectable, isSelected, onSelect } = select;
    return (
      <TableCell {...props}>
        <HStack>
          <Checkbox checked={isSelected} disabled={!isSelectable} onChange={() => onSelect(row)} />
          <Box {...selectableProps}>{inside}</Box>
        </HStack>
      </TableCell>
    );
  }

  if (select) {
    props = { ...props, ...selectableProps };
  }

  return <TableCell {...props}>{inside}</TableCell>;
}
