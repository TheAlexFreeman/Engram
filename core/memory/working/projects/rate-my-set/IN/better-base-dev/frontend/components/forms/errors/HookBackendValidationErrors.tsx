import React, { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';

import { Box, List, Text, TextProps } from '@chakra-ui/react';
import { noCase } from 'change-case';
import isEqual from 'lodash-es/isEqual';
import { Control, FieldPath, FieldValues, Path, useFormContext, useWatch } from 'react-hook-form';
import { titleCase } from 'title-case';

import { ValidationError } from '@/api/types/api';

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface ErrorBlockProps extends TextProps {}

export type HookFormBackendValidationErrorsHandlerProps<
  TFieldValues extends FieldValues = FieldValues,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TContext = any,
> = {
  error: ValidationError | null;
  setError: (error: ValidationError | null) => void;
  control: Control<TFieldValues, TContext>;
  errorBlockProps?: ErrorBlockProps;
  watchOnly?: FieldPath<FieldValues>[];
} & ErrorBlockProps;

export default function HookFormBackendValidationErrorsHandler<
  TFieldValues extends FieldValues = FieldValues,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TContext = any,
>({
  error,
  setError,
  control,
  errorBlockProps,
  watchOnly,
  ...rest
}: HookFormBackendValidationErrorsHandlerProps<TFieldValues, TContext>) {
  const clearError = useCallback(() => {
    setError(null);
  }, [setError]);

  const hasError = useMemo(() => error != null, [error]);

  // @ts-expect-error - TypeScript overload mismatch
  const watchResult = useWatch<TFieldValues>({
    ...(watchOnly == null ? {} : { name: watchOnly }),
    control,
  });
  const formContext = useFormContext<TFieldValues>();
  const formValues =
    watchOnly == null
      ? formContext.getValues()
      : formContext.getValues(watchOnly as Path<TFieldValues>[]);
  // See https://www.react-hook-form.com/api/usewatch/ and the note about "useWatch's
  // execution order matters" for why we did this.
  // Note: When `watchOnly` is provided, both values may be arrays. Using Object.assign
  // to merge them works for the isEqual comparison even if the result is `{0: v1, 1: v2}`.
  const currentValues = useMemo(
    () => Object.assign({}, watchResult, formValues),
    [watchResult, formValues],
  );

  const [lastSnapshot, setLastSnapshot] = useState(currentValues);
  useEffect(() => {
    if (!isEqual(lastSnapshot, currentValues)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLastSnapshot(currentValues);
    }
  }, [lastSnapshot, currentValues]);

  useEffect(() => {
    if (hasError && !isEqual(lastSnapshot, currentValues)) {
      return () => clearError();
    }
  }, [hasError, lastSnapshot, currentValues, clearError]);

  const sendErrorBlockProps = { ...rest, ...(errorBlockProps || {}) };

  return error == null ? null : (
    <BackendValidationErrorsBlock error={error} {...sendErrorBlockProps} />
  );
}

interface BackendValidationErrorsBlockProps extends TextProps {
  error: ValidationError;
}

export const BackendValidationErrorsBlock: React.FC<BackendValidationErrorsBlockProps> = ({
  error,
  ...rest
}) => {
  const { css: passedCss, ...restMinusSx } = rest;

  const errorDisplay: ReactNode = useMemo(() => {
    const { fieldErrors, nonFieldErrors } = error;

    return (
      <>
        {!error.hasFieldErrors && error.hasNonFieldErrors && (
          <NonFieldErrorsBlock title={null} errors={nonFieldErrors} />
        )}
        {error.hasFieldErrors &&
          Object.entries(fieldErrors).map(([fieldName, errors], index) => (
            <FieldErrorsBlock key={index} fieldName={fieldName} errors={errors} />
          ))}
        {error.hasFieldErrors && error.hasNonFieldErrors && (
          <NonFieldErrorsBlock
            title={error.hasExactlyOneNonFieldError ? 'Other Error' : 'Other Errors'}
            errors={nonFieldErrors}
          />
        )}
      </>
    );
  }, [error]);

  return (
    <Box color="fg.error" css={passedCss || {}} {...restMinusSx}>
      {errorDisplay}
    </Box>
  );
};

const FieldErrorsBlock: React.FC<{ fieldName: string; errors: string[] }> = ({
  fieldName,
  errors,
}) => {
  const fieldTitle = titleCase(noCase(fieldName));
  if (errors.length === 1) {
    return (
      <Text fontSize="md">
        <strong>{fieldTitle}: </strong>
        {errors[0]}
      </Text>
    );
  }
  return (
    <Box>
      <Text fontSize="md">
        <strong>{fieldTitle}: </strong>
      </Text>
      <List.Root fontSize="md">
        {errors.map((error, index) => (
          <List.Item key={index}>{error}</List.Item>
        ))}
      </List.Root>
    </Box>
  );
};

const NonFieldErrorsBlock: React.FC<{ title: string | null | undefined; errors: string[] }> = ({
  title,
  errors,
}) => {
  if (errors.length === 1) {
    return (
      <Text fontSize="md">
        {title && <strong>{title}: </strong>}
        {errors[0]}
      </Text>
    );
  }
  return (
    <Box>
      {title && (
        <Text fontSize="md">
          <strong>{title}: </strong>
        </Text>
      )}
      <List.Root fontSize="md">
        {errors.map((error, index) => (
          <List.Item key={index}>{error}</List.Item>
        ))}
      </List.Root>
    </Box>
  );
};
