import { type Account } from './accounts';
import { type Role } from './memberships';
import { type User } from './users';

export enum InvitationStatus {
  OPEN = 'open',
  ACCEPTED = 'accepted',
  DECLINED = 'declined',
  EXPIRED = 'expired',
}

export interface Invitation {
  id: number;
  account: Account;
  invitedBy: User;
  email: string;
  name: string;
  role: Role;
  roleDisplay: string;
  user: User | null;
  acceptedAt: string | null; // datetime string
  expiresAt: string | null; // datetime string
  deliveryMethod: 'email';
  lastSentAt: string | null; // datetime string
  created: string; // datetime string
  isAccepted: boolean;
  isDeclined: boolean;
  isExpired: boolean;
  isPastFollowWindow: boolean;
  status: InvitationStatus;
  statusDisplay: string;
  teamDisplayName: string;
  isUsingFallbackTeamDisplayName: boolean;
  headline: string;
}

export const allInvitationStatuses: readonly [
  InvitationStatus.OPEN,
  InvitationStatus.ACCEPTED,
  InvitationStatus.DECLINED,
  InvitationStatus.EXPIRED,
] = [
  InvitationStatus.OPEN,
  InvitationStatus.ACCEPTED,
  InvitationStatus.DECLINED,
  InvitationStatus.EXPIRED,
] as const;

export const invitationStatusChoices: readonly [
  { label: string; value: InvitationStatus.OPEN },
  { label: string; value: InvitationStatus.ACCEPTED },
  { label: string; value: InvitationStatus.DECLINED },
  { label: string; value: InvitationStatus.EXPIRED },
] = [
  { label: 'Open', value: InvitationStatus.OPEN },
  { label: 'Accepted', value: InvitationStatus.ACCEPTED },
  { label: 'Declined', value: InvitationStatus.DECLINED },
  { label: 'Expired', value: InvitationStatus.EXPIRED },
] as const;
