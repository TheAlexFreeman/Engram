import { Dispatch, SetStateAction, useCallback, useMemo, useState } from 'react';

import { FieldValues } from 'react-hook-form';

import { PermissionsError, ServerError, ValidationError } from '@/api/types/api';
import HookFormBackendValidationErrorsHandler, {
  HookFormBackendValidationErrorsHandlerProps,
} from '@/components/forms/errors/HookBackendValidationErrors';

import { NotFoundError } from '../../../api/types/api';

export type UseHookFormBackendErrorsDisplayProps<
  TFieldValues extends FieldValues = FieldValues,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TContext = any,
> = Omit<HookFormBackendValidationErrorsHandlerProps<TFieldValues, TContext>, 'error' | 'setError'>;

interface ErrorWrappedRequestResultWithError<T> {
  hasError: true;
  error: ValidationError;
  originalError: ValidationError | PermissionsError | ServerError;
  result?: T | null;
}

interface ErrorWrappedRequestResultWithoutError<T> {
  hasError: false;
  error: null;
  result: T;
}

export type ErrorWrappedRequestResult<T> =
  | ErrorWrappedRequestResultWithError<T>
  | ErrorWrappedRequestResultWithoutError<T>;

export default function useHookFormBackendErrorsDisplay<
  TFieldValues extends FieldValues = FieldValues,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TContext = any,
>({ control }: UseHookFormBackendErrorsDisplayProps<TFieldValues, TContext>) {
  const [validationError, setValidationError] = useState<ValidationError | null>(null);

  const errorWrappedRequest = useCallback(
    async function <T>(awaitable: Promise<T>): Promise<ErrorWrappedRequestResult<T>> {
      const awaitedValue = await wrapRequestWithErrorHandling({ awaitable, setValidationError });
      return awaitedValue;
    },
    [setValidationError],
  );

  const BackendErrorsDisplay = useMemo(() => {
    function WrappedHookFormBackendValidationErrorsHandler(
      props: Omit<UseHookFormBackendErrorsDisplayProps, 'control'>,
    ) {
      return (
        <HookFormBackendValidationErrorsHandler
          control={control}
          error={validationError}
          setError={setValidationError}
          {...props}
        />
      );
    }
    return WrappedHookFormBackendValidationErrorsHandler;
  }, [control, validationError, setValidationError]);

  return {
    validationError,
    setValidationError,
    errorWrappedRequest,
    BackendErrorsDisplay,
  };
}

interface WrapRequestWithErrorHandlingArgs<T> {
  awaitable: Promise<T>;
  setValidationError?: Dispatch<SetStateAction<ValidationError | null>>;
}

export async function wrapRequestWithErrorHandling<T>({
  awaitable,
  setValidationError,
}: WrapRequestWithErrorHandlingArgs<T>): Promise<ErrorWrappedRequestResult<T>> {
  try {
    const result = await awaitable;

    if (setValidationError != null) {
      setValidationError(null);
    }

    return { error: null, hasError: false, result };
  } catch (e) {
    let ve: ValidationError | null = null;
    if (e instanceof ValidationError) {
      ve = e;
    } else if (e instanceof PermissionsError) {
      ve = e.asValidationError();
    } else if (e instanceof NotFoundError) {
      ve = e.asValidationError();
    } else if (e instanceof ServerError) {
      ve = e.asValidationError();
    } else {
      throw e;
    }

    if (setValidationError != null) {
      if (ve == null) {
        setValidationError(null);
      } else {
        setValidationError(ve);
      }
    }

    return { hasError: true, error: ve, originalError: e, result: null };
  }
}
