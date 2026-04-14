import { ComponentProps, ComponentType, ReactNode, useMemo } from 'react';

import {
  Field as ChakraField,
  FieldErrorTextProps,
  FieldHelperTextProps,
  FieldLabelProps,
  FieldRootProps,
  chakra,
} from '@chakra-ui/react';
import { CreatableSelect, Select } from 'chakra-react-select';
import { FieldValues, UseControllerProps, useController, useFormContext } from 'react-hook-form';

export type ReactSelectProps = ComponentProps<typeof Select>;
export type ReactCreatableSelectProps = ComponentProps<typeof CreatableSelect>;

export interface ReactSelectFieldBaseProps<T extends string> {
  // NOTE: `name`, `required`, `placeholder`, `disabled`, `required` etc., could be
  // within `slotProps.select` instead but they're going to be so commonly used I think
  // it's easier to make shortcuts at the top (and potentially helps with the generics
  // as well).
  name: T;
  label: string;
  id?: string;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  readonly?: boolean;
  disableLabelFocus?: boolean;
  rules?: UseControllerProps<FieldValues, T>['rules'];
  slots?: {
    SelectWrapper: ComponentType<{ children: ReactNode }>;
  };
  slotProps?: {
    fieldRoot?: FieldRootProps;
    fieldLabel?: FieldLabelProps;
    select?: ReactSelectProps;
    helperText?: FieldHelperTextProps;
    errorText?: FieldErrorTextProps;
  };
}

export type ReactSelectFieldRegularProps<T extends string> = ReactSelectFieldBaseProps<T> & {
  isCreatable?: false;
  slotProps?: ReactSelectFieldBaseProps<T>['slotProps'] & {
    select?: ReactSelectProps;
  };
};

export type ReactSelectFieldCreatableProps<T extends string> = ReactSelectFieldBaseProps<T> & {
  isCreatable: true;
  slotProps?: ReactSelectFieldBaseProps<T>['slotProps'] & {
    select?: ReactCreatableSelectProps;
  };
};

export type ReactSelectFieldProps<T extends string> =
  | ReactSelectFieldRegularProps<T>
  | ReactSelectFieldCreatableProps<T>;

export default function ReactSelectField<T extends string>({
  name,
  label,
  id,
  helperText,
  required,
  disabled,
  placeholder,
  readonly,
  disableLabelFocus,
  rules,
  isCreatable,
  slots,
  slotProps,
}: ReactSelectFieldProps<T>) {
  const idToUse = id || slotProps?.select?.id || name;

  const { setFocus, control } = useFormContext();

  const {
    field: { onChange, onBlur, value, ref },
    fieldState: { invalid, error },
  } = useController({
    name,
    control,
    rules,
  });

  const errorMessage = error?.message;
  const hasError = !!error && !!errorMessage;

  // Optional indicator calculations on when to hide it, as of the time of writing.
  const labelLength = label.length;
  const optionalLength = 'Optional'.length;
  // Give at least 2 characters of space between the label and the optional indicator.
  const hideOptionalIndicatorLength = `${labelLength + optionalLength + 2}ch`;

  const defaultOptionalIndicator = useMemo(
    () => (
      <chakra.span
        textStyle="body3"
        color="text.lighter"
        role="presentation"
        aria-hidden="true"
        className="chakra-form__optional-indicator optionalIndicator"
      >
        Optional
      </chakra.span>
    ),
    [],
  );

  const selectProps = useMemo<ReactSelectProps>(() => {
    const holder: ReactSelectProps = { name };
    if (placeholder != null) {
      holder.placeholder = placeholder;
    } else if (label != null) {
      holder.placeholder = label;
    }
    if (readonly != null) {
      holder.readOnly = readonly;
    }
    const propsFromController = {
      onChange,
      onBlur,
      value,
      ref,
    };
    const propsFromSlot = { ...slotProps?.select } as ReactSelectProps;
    if (!propsFromSlot.styles) propsFromSlot.styles = {};
    if (!propsFromSlot.selectedOptionColorPalette) {
      propsFromSlot.selectedOptionColorPalette = 'primary';
    }
    if (!propsFromSlot.chakraStyles) {
      propsFromSlot.chakraStyles = {
        control: (provided, state) => ({
          ...provided,
          borderBottomLeftRadius: state.menuIsOpen ? 0 : 'md',
          borderBottomRightRadius: state.menuIsOpen ? 0 : 'md',
          transitionDuration: '0',
        }),
        menu: (provided) => ({
          ...provided,
          my: 0,
          ml: '-1px',
          width: 'calc(100% + 2px)',
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
          shadow: '0',
          borderWidth: '2px',
          borderColor: 'var(--chakra-colors-primary-bg-main)',
          borderTop: '1px',
          borderBottomRadius: 'md',
        }),
        menuList: (provided) => ({
          ...provided,
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
          borderWidth: 0,
        }),
        option: (provided) => ({
          ...provided,
          color: 'var(--chakra-colors-text-main)',
        }),
      };
    }

    return { ...holder, ...propsFromController, ...propsFromSlot, id: idToUse };
  }, [
    name,
    placeholder,
    label,
    readonly,
    slotProps?.select,
    idToUse,
    onChange,
    onBlur,
    value,
    ref,
  ]);

  const labelProps = useMemo<FieldLabelProps>(() => {
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
    const Wrapped = isCreatable ? CreatableSelect : Select;
    if (Wrapper == null) {
      return <Wrapped {...selectProps} />;
    }
    return (
      <Wrapper>
        <Wrapped {...selectProps} />
      </Wrapper>
    );
  }, [slots?.SelectWrapper, selectProps, isCreatable]);

  return (
    <ChakraField.Root
      required={required}
      disabled={disabled}
      invalid={invalid}
      readOnly={readonly}
      {...slotProps?.fieldRoot}
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
      <ChakraField.Label {...labelProps}>
        {label}
        {!required && defaultOptionalIndicator}
      </ChakraField.Label>
      {renderedSelect}
      {!hasError && helperText && (
        <ChakraField.HelperText {...helperTextProps}>{helperText}</ChakraField.HelperText>
      )}
      {hasError && <ChakraField.ErrorText {...errorProps}>{errorMessage}</ChakraField.ErrorText>}
    </ChakraField.Root>
  );
}
