import DataList, { ColumnDef, DataListConfig, DataListSlotProps, Row } from './DataList';

export type SingleSelectableDataListProps<T extends object> = {
  columnDefs: ColumnDef<T>[];
  rows: Row<T>[];
  selectedRow?: Row<T>;
  onRowSelected: (row: Row<T>) => void;
  exclude?: ((row: Row<T>) => boolean) | undefined;
  config?: DataListConfig<T>;
  slotProps?: DataListSlotProps<T>;
};

export type MultiSelectableDataListProps<T extends object> = {
  columnDefs: ColumnDef<T>[];
  rows: Row<T>[];
  selectedRows: Row<T>[];
  onRowSelected: (row: Row<T>) => void;
  exclude?: ((row: Row<T>) => boolean) | undefined;
  config?: DataListConfig<T>;
  slotProps?: DataListSlotProps<T>;
};

export function SingleSelectableDataList<T extends object>({
  columnDefs,
  rows,
  selectedRow,
  onRowSelected,
  exclude,
  config = {},
  slotProps = {},
}: SingleSelectableDataListProps<T>) {
  const props = {
    columnDefs,
    rows,
    config,
    slotProps,
    select: {
      exclude,
      onRowSelected,
      selectedRows: selectedRow ? [selectedRow] : [],
    },
  };
  return <DataList {...props} />;
}

export function MultiSelectableDataList<T extends object>({
  columnDefs,
  rows,
  selectedRows,
  exclude,
  onRowSelected,
  config = {},
  slotProps = {},
}: MultiSelectableDataListProps<T>) {
  const props = {
    columnDefs,
    rows,
    config,
    slotProps,
    select: {
      selectedRows,
      exclude,
      onRowSelected,
    },
  };
  return <DataList {...props} />;
}
