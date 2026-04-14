import {
  NotAuthenticatedError,
  NotFoundError,
  PermissionsError,
  ValidationError,
} from '@/api/types/api';

export const defaultRetry = (failureCount: number, error: Error) => {
  if (
    error instanceof ValidationError ||
    error instanceof NotAuthenticatedError ||
    error instanceof PermissionsError ||
    error instanceof NotFoundError
  )
    return false;
  return failureCount < 3;
};
