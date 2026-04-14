import { apiRequest } from '@/api/request';
import { Account } from '@/api/types/accounts/accounts';
import { Membership, Role } from '@/api/types/accounts/memberships';
import { User } from '@/api/types/accounts/users';
import { getQueryParamsString } from '@/utils/urlQueryParams';

export type MembershipListQueryParamsFromUser = {
  accountId?: undefined;
  userId: User['id'] | string;
};

export type MembershipListQueryParamsFromAccount = {
  accountId: Account['id'] | string;
  userId?: User['id'] | string;
};

export type MembershipListQueryParams =
  | MembershipListQueryParamsFromUser
  | MembershipListQueryParamsFromAccount;

export type MembershipListQueryReturnTypeFromUser = Omit<Membership, 'user'>[];

export type MembershipListQueryReturnTypeFromAccount = Omit<Membership, 'account'>[];

export type MembershipListQueryReturnType =
  | MembershipListQueryReturnTypeFromUser
  | MembershipListQueryReturnTypeFromAccount;

export class MembershipService {
  async list({
    params,
  }: {
    params: MembershipListQueryParamsFromUser;
  }): Promise<MembershipListQueryReturnTypeFromUser>;
  async list({
    params,
  }: {
    params: MembershipListQueryParamsFromAccount;
  }): Promise<MembershipListQueryReturnTypeFromAccount>;

  async list({ params }: { params: MembershipListQueryParams }) {
    const paramsStr = getQueryParamsString(params);

    const objs = await apiRequest('GET', `/api/memberships?${paramsStr}`, {});

    if (params?.accountId == null) {
      return objs as MembershipListQueryReturnTypeFromUser;
    }
    return objs as MembershipListQueryReturnTypeFromAccount;
  }

  async get(id: number): Promise<Membership> {
    const obj = await apiRequest('GET', `/api/memberships/${id}`);

    return obj as Membership;
  }

  async updateRole(id: number, role: Role): Promise<Membership> {
    const response = await apiRequest('POST', `/api/memberships/${id}/update-role`, {
      json: { role },
    });

    return response as Membership;
  }

  async select(id: number): Promise<Membership> {
    const obj = await apiRequest('POST', `/api/memberships/${id}/select`, {
      json: {},
    });

    return obj as Membership;
  }

  async delete(id: number) {
    await apiRequest('DELETE', `/api/memberships/${id}`);
  }
}

const membershipService = new MembershipService();
export default membershipService;
