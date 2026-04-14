import { type Account } from './accounts';
import { type User } from './users';

export enum Role {
  MEMBER = 'member',
  OWNER = 'owner',
}

export interface Membership {
  id: number;
  account: Account;
  user: User;
  role: Role;
  roleDisplay: string;
}

export const allRoles: readonly [Role.MEMBER, Role.OWNER] = [Role.MEMBER, Role.OWNER] as const;

export const roleChoices: readonly [
  { label: string; value: Role.MEMBER },
  { label: string; value: Role.OWNER },
] = [
  { label: 'Member', value: Role.MEMBER },
  { label: 'Owner', value: Role.OWNER },
] as const;
