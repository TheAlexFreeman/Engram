import { noCase } from 'change-case';
import { titleCase } from 'title-case';

import {
  NotAuthenticatedError,
  NotFoundError,
  PermissionsError,
  ServerError,
  ValidationError,
} from '../api/types/api';

export function getBestSingleErrorMessageFor(
  e: ValidationError | NotAuthenticatedError | PermissionsError | ServerError | Error,
): string {
  const fallback =
    'An unexpected server error occurred. Please try again. If the ' +
    'issue continues please contact support.';

  if (e instanceof ValidationError) {
    if (e.hasNonFieldErrors) return e.firstNonFieldError || fallback;
    if (e.hasFieldErrors) {
      const [key, message] = e.firstFieldError;
      if (key && message) {
        const keyTitle = titleCase(noCase(key));
        if (key && message) return `${keyTitle}: ${message}`;
      }
    }
    return fallback;
  } else if (e instanceof NotAuthenticatedError) {
    return e.errorMessage || fallback;
  } else if (e instanceof PermissionsError) {
    return e.errorMessage || fallback;
  } else if (e instanceof NotFoundError) {
    return getBestSingleErrorMessageFor(e.asValidationError());
  } else if (e instanceof ServerError) {
    return getBestSingleErrorMessageFor(e.asValidationError());
  }

  return fallback;
}
