import { type Membership } from './accounts/memberships';
import { type CsrfToken } from './auth/csrf';
import { type AuthenticatedUser, type UnauthenticatedUser } from './auth/users';
import { type ServerMessage } from './messages';
import { type SessionData } from './sessions';

export interface ExtraData {
  signaling: {
    immediatelyRedirectTo?: string;
  };
  [key: string]: unknown;
}

export interface BaseInitialData {
  messages: ServerMessage[];
  csrfToken: CsrfToken;
  memberships: Membership[];
  session: SessionData;
  extra: ExtraData;
}

export interface AuthenticatedInitialData extends BaseInitialData {
  user: AuthenticatedUser;
  currentMembership: Membership;
}

export interface UnauthenticatedInitialData extends BaseInitialData {
  user: UnauthenticatedUser;
  currentMembership: null;
}

export type InitialData = AuthenticatedInitialData | UnauthenticatedInitialData;
