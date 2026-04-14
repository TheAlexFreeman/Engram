import type { Account } from '@/api/types/accounts/accounts';
import type { Membership } from '@/api/types/accounts/memberships';
import type { AuthenticatedUser } from '@/api/types/auth/users';

import { apiRequest } from '@/api/request';
import { currentMembershipAtom, initialDataAtom, membershipsAtom } from '@/state/auth';
import store from '@/state/store';

export interface AccountCreatePayload {
  accountType: Account['accountType'];
  name: string;
}

export type AccountCreateResult = Account & { membershipCreated: Membership };

export interface CheckUserDeletionCaseResult {
  isOwner: boolean;
  hasOtherUsers: boolean;
  willOnlyDeleteSelf: boolean;
  willDeleteAccount: boolean;
  willDeleteOtherUsers: boolean;
  otherMembershipsThatWouldBeDeleted: Membership[];
  otherUsersThatWouldBeDeleted: AuthenticatedUser[];
}

export interface UserDeletionResult {
  wasOwner: boolean;
  hadOtherOwners: boolean;
  deletedOnlySelf: boolean;
  deletedAccount: boolean;
  deletedOtherUsers: boolean;
  numOtherDeletedMemberships: number;
  numOtherDeletedUsers: number;
  deleteResults: null;
  otherUsersDeleteResults: null;
}

export interface AccountUpdatePayload {
  name?: string;
}

export class AccountService {
  async create(payload: AccountCreatePayload): Promise<AccountCreateResult> {
    const response = (await apiRequest('POST', `/api/accounts`, {
      json: payload,
    })) as AccountCreateResult;

    const initialData = store.get(initialDataAtom);
    store.set(initialDataAtom, initialData, { justCreatedAccount: response });

    return response;
  }

  async checkDelete(userId: number): Promise<CheckUserDeletionCaseResult> {
    const checkResult = (await apiRequest(
      'GET',
      `/api/users/${userId}/check-delete-case`,
      {},
    )) as CheckUserDeletionCaseResult;
    return checkResult;
  }

  async get(accountId: string): Promise<Account> {
    const accountResult = (await apiRequest('GET', `/api/accounts/${accountId}`, {})) as Account;
    return accountResult;
  }

  async performDelete(userId: number): Promise<UserDeletionResult> {
    const deleteResult = (await apiRequest(
      'DELETE',
      `/api/users/${userId}`,
      {},
    )) as UserDeletionResult;

    return deleteResult;
  }

  async performRemoveMember(membershipId: number): Promise<UserDeletionResult> {
    const deleteResult = (await apiRequest(
      'DELETE',
      `/api/membership/${membershipId}`,
      {},
    )) as UserDeletionResult;

    return deleteResult;
  }

  async update(id: Account['id'], payload: AccountUpdatePayload): Promise<Account> {
    const obj = (await apiRequest('PATCH', `/api/accounts/${id}`, {
      json: payload,
    })) as Account;
    const memberships = store.get(membershipsAtom);
    const currentMembership = store.get(currentMembershipAtom);

    const membershipToUpdate = memberships.find((m) => m.account.id === obj.id);

    if (membershipToUpdate) {
      const updatedMembership = { ...membershipToUpdate, account: obj };
      store.set(membershipsAtom, 'remove', membershipToUpdate);
      store.set(membershipsAtom, 'add', updatedMembership);
      if (currentMembership?.account.id === obj.id) {
        store.set(currentMembershipAtom, updatedMembership);
      }
    }

    return obj;
  }

  async updateUploadedProfileImage(id: number, pi: File) {
    const body = new FormData();
    body.append('uploadedProfileImage', pi);
    const account = (await apiRequest('POST', `/api/accounts/${id}/update-uploaded-profile-image`, {
      body,
      responseJson: true,
      isFileUpload: true,
    })) as Account;

    const current = store.get(currentMembershipAtom);
    if (current != null && current.account.id == id) {
      store.set(currentMembershipAtom, { ...current, account });
    }

    return account;
  }

  async deleteUploadedProfileImage(id: Account['id']) {
    const account = (await apiRequest('POST', `/api/accounts/${id}/delete-uploaded-profile-image`, {
      responseJson: true,
    })) as Account;

    const current = store.get(currentMembershipAtom);
    if (current != null && current.account.id == id) {
      store.set(currentMembershipAtom, { ...current, account });
    }

    return account;
  }
}

const accountService = new AccountService();
export default accountService;
