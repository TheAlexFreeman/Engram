import { type Account } from './accounts';
import { type Membership } from './memberships';

export interface User {
  id: number;
  email: string;
  emailIsVerified: boolean;
  emailVerifiedAsOf: string; // datetime string
  name: string;
  isAuthenticated: true;
  isActive: boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  dateJoined: string; // datetime string
  lastLogin: string; // datetime string
  uploadedProfileImage: string;
}

export type UserAutomatedPreDeleteActionType =
  | 'delete-account'
  | 'delete-membership'
  | 'delete-user';

export type UserManualPreDeleteActionType =
  | 'transfer-ownership'
  | 'delete-account'
  | 'notify-other-owners';

export type UserManualPreDeleteWarningType = 'other-owners' | 'other-members';

export type ManualActionsType = Record<
  Account['id'],
  Record<UserManualPreDeleteWarningType, UserManualPreDeleteActionType[]>
>;

export type AutomatedActionsType = Record<Account['id'], UserAutomatedPreDeleteActionType>;

export interface CheckUserDeleteResult {
  user: User;
  memberships: Omit<Membership, 'account'>[];
  canDeleteUser: boolean;
  shouldOfferManualActionsBeforeDeleting: boolean;
  automatedActionsPlanned: AutomatedActionsType;
  manualActionsRequired: ManualActionsType;
  manualActionsOffered: ManualActionsType;
  accountIdsAllCleared: Account['id'][];
}
