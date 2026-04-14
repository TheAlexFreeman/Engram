import { ComponentType, ReactNode, useMemo } from 'react';

import {
  Field as ChakraField,
  FieldErrorTextProps,
  FieldHelperTextProps,
  FieldLabelProps,
  FieldRootProps,
  Input,
  InputProps,
  chakra,
} from '@chakra-ui/react';
import { FieldValues, RegisterOptions, useFormContext } from 'react-hook-form';

import { InputGroupProps } from '@/components/ui/input-group';

export interface InputFieldProps<T extends string> {
  // NOTE: `name`, `required`, `placeholder`, `disabled`, `required` `type`, etc., could
  // be within `slotProps.input` instead but they're going to be so commonly used I
  // think it's easier to make shortcuts at the top (and potentially helps with the
  // generics as well).
  name: T;
  label: string;
  id?: string;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  type?: string;
  readonly?: boolean;
  autocomplete?: string;
  disableLabelFocus?: boolean;
  slots?: {
    InputWrapper: ComponentType<{ children: ReactNode }>;
  };
  slotProps?: {
    fieldRoot?: FieldRootProps;
    fieldLabel?: FieldLabelProps;
    input?: InputProps;
    inputGroup?: Partial<InputGroupProps>;
    register?: RegisterOptions<FieldValues, T>;
    helperText?: FieldHelperTextProps;
    errorText?: FieldErrorTextProps;
  };
}

export default function InputField<T extends string>({
  name,
  label,
  id,
  helperText,
  required,
  disabled,
  placeholder,
  type,
  readonly,
  autocomplete,
  disableLabelFocus,
  slots,
  slotProps,
}: InputFieldProps<T>) {
  const idToUse = id || slotProps?.input?.id || name;

  const {
    register,
    formState: { errors },
    setFocus,
  } = useFormContext();

  const error = errors[name];
  const errorMessage = error?.message as string | undefined;
  const hasError = !!error && !!errorMessage;

  // Optional indicator calculations on when to hide it, as of the time of writing.
  const labelLength = label.length;
  const optionalLength = 'Optional'.length;
  // Give at least 2 characters of space between the label and the optional indicator.
  const hideOptionalIndicatorLength = `${labelLength + optionalLength + 2}ch`;

  const fieldProps = useMemo<FieldRootProps>(() => {
    const holder: FieldRootProps = { required, disabled, invalid: hasError, readOnly: readonly };
    const propsFromSlot = slotProps?.fieldRoot || {};
    return { ...holder, ...propsFromSlot, id: idToUse };
  }, [required, disabled, hasError, readonly, slotProps?.fieldRoot, idToUse]);

  const initialInputProps = useMemo<InputProps>(() => {
    const holder: InputProps = { name };
    if (placeholder != null) {
      holder.placeholder = placeholder;
    } else if (label != null) {
      holder.placeholder = label;
    }
    if (type != null) {
      holder.type = type;
    }
    if (readonly != null) {
      holder.readOnly = readonly;
    }
    if (autocomplete != null) {
      holder.autoComplete = autocomplete;
    }
    const propsFromSlot = slotProps?.input || {};
    return { ...holder, ...propsFromSlot, id: idToUse };
  }, [name, placeholder, label, type, readonly, autocomplete, slotProps?.input, idToUse]);

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

  const registerProps = useMemo<RegisterOptions<FieldValues, T>>(() => {
    return slotProps?.register || {};
  }, [slotProps?.register]);

  const helperTextProps = useMemo<FieldHelperTextProps>(() => {
    return slotProps?.helperText || {};
  }, [slotProps?.helperText]);

  const errorProps = useMemo<FieldErrorTextProps>(() => {
    return slotProps?.errorText || {};
  }, [slotProps?.errorText]);

  const finalInputProps = useMemo<InputProps>(() => {
    const registerValue = register(name, registerProps);
    return { ...initialInputProps, ...registerValue };
  }, [register, name, registerProps, initialInputProps]);

  const renderedInput = useMemo(() => {
    const Wrapper = slots?.InputWrapper;
    if (Wrapper == null) {
      return <Input {...finalInputProps} />;
    }
    return (
      <Wrapper>
        <Input {...finalInputProps} />
      </Wrapper>
    );
  }, [slots?.InputWrapper, finalInputProps]);

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
      {renderedInput}
      {!hasError && helperText && (
        <ChakraField.HelperText {...helperTextProps}>{errorMessage || ''}</ChakraField.HelperText>
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
