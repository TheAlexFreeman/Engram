export enum AccountType {
  PERSONAL = 'personal',
  TEAM = 'team',
}

export interface Account {
  id: number;
  name: string;
  fallbackName: string;
  // At the time of writing this is equivalent to `name || fallbackName`.
  displayName: string;
  accountType: AccountType;
  accountTypeDisplay: string;
  created: string; // datetime string
  uploadedProfileImage: string;
}

export const allAccountTypes: readonly [AccountType.PERSONAL, AccountType.TEAM] = [
  AccountType.PERSONAL,
  AccountType.TEAM,
] as const;

export const accountTypeChoices: readonly [
  { label: string; value: AccountType.PERSONAL },
  { label: string; value: AccountType.TEAM },
] = [
  { label: 'Personal', value: AccountType.PERSONAL },
  { label: 'Team', value: AccountType.TEAM },
] as const;
