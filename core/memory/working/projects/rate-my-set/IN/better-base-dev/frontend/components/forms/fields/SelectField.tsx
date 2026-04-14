import { ComponentType, ReactNode, useMemo } from 'react';

import {
  Field as ChakraField,
  FieldErrorTextProps,
  FieldHelperTextProps,
  FieldLabelProps,
  FieldRootProps,
  chakra,
  createListCollection,
} from '@chakra-ui/react';
import {
  FieldPath,
  FieldValues,
  RegisterOptions,
  useController,
  useFormContext,
} from 'react-hook-form';

import {
  SelectContent,
  SelectItem,
  SelectLabel,
  SelectRoot,
  SelectTrigger,
  SelectValueText,
} from '@/components/ui/select';

export interface SelectOption {
  label: string;
  value: string;
}

export interface SelectFieldProps<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  name: TName;
  label: string;
  options: SelectOption[];
  id?: string;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  readonly?: boolean;
  disableLabelFocus?: boolean;
  clearable?: boolean;
  multiple?: boolean;
  rules?: RegisterOptions<TFieldValues, TName>;
  slots?: {
    SelectWrapper: ComponentType<{ children: ReactNode }>;
  };
  slotProps?: {
    fieldRoot?: FieldRootProps;
    fieldLabel?: FieldLabelProps;
    select?: {
      positioning?: Record<string, unknown>;
      [key: string]: unknown;
    };
    helperText?: FieldHelperTextProps;
    errorText?: FieldErrorTextProps;
  };
}

export default function SelectField<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  name,
  label,
  options,
  id,
  helperText,
  required,
  disabled,
  placeholder,
  readonly,
  disableLabelFocus,
  clearable,
  multiple,
  rules,
  slots,
  slotProps,
}: SelectFieldProps<TFieldValues, TName>) {
  const idToUse = id || name;

  const { control, setFocus } = useFormContext<TFieldValues>();

  const {
    field: { onChange, onBlur, value, ref },
    fieldState: { error },
  } = useController({
    name,
    control,
    rules,
  });

  const errorMessage = error?.message;
  const hasError = !!error && !!errorMessage;

  // Optional indicator calculations
  const labelLength = label.length;
  const optionalLength = 'Optional'.length;
  const hideOptionalIndicatorLength = `${labelLength + optionalLength + 2}ch`;

  const collection = useMemo(() => {
    return createListCollection({
      items: options,
    });
  }, [options]);

  const fieldProps = useMemo<FieldRootProps>(() => {
    const holder: FieldRootProps = { required, disabled, invalid: hasError, readOnly: readonly };
    const propsFromSlot = slotProps?.fieldRoot || {};
    return { ...holder, ...propsFromSlot, id: idToUse };
  }, [required, disabled, hasError, readonly, slotProps?.fieldRoot, idToUse]);

  const fieldLabelProps = useMemo<FieldLabelProps>(() => {
    const defaultOnClick = (e: React.MouseEvent<HTMLLabelElement>) => {
      e.preventDefault();
      if (!disableLabelFocus) setFocus(name);
    };
    const holder: FieldLabelProps = {
      htmlFor: idToUse,
      onClick: defaultOnClick,
      ...(!required && {
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        width: '100%',
        marginRight: 0,
      }),
    };
    return { ...holder, ...(slotProps?.fieldLabel || {}) };
  }, [idToUse, disableLabelFocus, setFocus, name, required, slotProps?.fieldLabel]);

  const helperTextProps = useMemo<FieldHelperTextProps>(() => {
    return slotProps?.helperText || {};
  }, [slotProps?.helperText]);

  const errorProps = useMemo<FieldErrorTextProps>(() => {
    return slotProps?.errorText || {};
  }, [slotProps?.errorText]);

  const renderedSelect = useMemo(() => {
    const Wrapper = slots?.SelectWrapper;
    const select = (
      <SelectRoot
        ref={ref}
        name={name}
        value={value}
        disabled={disabled}
        multiple={multiple}
        collection={collection}
        onValueChange={({ value: nextValue }) => onChange(nextValue)}
        onInteractOutside={() => onBlur()}
        {...slotProps?.select}
      >
        <SelectLabel>{label}</SelectLabel>
        <SelectTrigger clearable={clearable}>
          <SelectValueText placeholder={placeholder || label} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} item={option}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </SelectRoot>
    );

    if (Wrapper == null) {
      return select;
    }

    return <Wrapper>{select}</Wrapper>;
  }, [
    slots?.SelectWrapper,
    ref,
    name,
    value,
    disabled,
    multiple,
    collection,
    onChange,
    onBlur,
    clearable,
    placeholder,
    label,
    options,
    slotProps?.select,
  ]);

  return (
    <ChakraField.Root
      {...fieldProps}
      css={{
        containerType: 'inline-size',
        containerName: 'form-control-container',
        [`@container form-control-container (inline-size < ${hideOptionalIndicatorLength})`]: {
          '.chakraForm__optionalIndicator': {
            display: 'none',
          },
        },
      }}
    >
      <ChakraField.Label {...fieldLabelProps}>
        {label}
        {!required && defaultOptionalIndicator}
      </ChakraField.Label>
      {renderedSelect}
      {!hasError && helperText && (
        <ChakraField.HelperText {...helperTextProps}>{helperText}</ChakraField.HelperText>
      )}
      {hasError && (
        <ChakraField.ErrorText {...errorProps}>{errorMessage || ''}</ChakraField.ErrorText>
      )}
    </ChakraField.Root>
  );
}

const defaultOptionalIndicator = (
  <chakra.span
    textStyle="body3"
    color="text.lighter"
    role="presentation"
    aria-hidden="true"
    className="chakra-form__optional-indicator optionalIndicator"
  >
    Optional
  </chakra.span>
);
