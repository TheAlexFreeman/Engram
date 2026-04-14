import { type User } from '../accounts/users';

export enum ChangeEmailRequestStatus {
  EMPTY = 'empty',
  PENDING = 'pending',
  EXPIRED = 'expired',
  SUCCESSFULLY_CHANGED = 'successfully_changed',
}

export interface ChangeEmailRequest {
  // NOTE: At the time of writing `-1` means it's a temporary instance on the backend.
  id: number;
  user: User['id'];
  fromEmail: string;
  toEmail: string;
  requestedAt: string | null; // datetime string (if non-null)
  successfullyChangedAt: string | null; // datetime string (if non-null)
  lastRequestedANewFromOrToEmailAt: string | null; // datetime string (if non-null)
  lastSentAChangeEmailAt: string | null; // datetime string (if non-null)
  lastSuccessfullyChangedAt: string | null; // datetime string (if non-null)
  status: ChangeEmailRequestStatus;
  status_display: string;

  isLoading?: true | null;
}
