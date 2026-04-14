import { apiRequest } from '@/api/request';
import { Account } from '@/api/types/accounts/accounts';
import { Invitation } from '@/api/types/accounts/invitations';
import { Membership, Role } from '@/api/types/accounts/memberships';
import { User } from '@/api/types/accounts/users';
import { membershipsAtom } from '@/state/auth';
import store from '@/state/store';
import { getQueryParamsString } from '@/utils/urlQueryParams';

export type InvitationListQueryParamsFromUser = {
  userId: User['id'] | string;
  accountId?: undefined;
  isAccepted?: boolean;
  isDeclined?: boolean;
  isExpired?: boolean;
};

export type InvitationListQueryParamsFromAccount = {
  accountId: Account['id'] | string;
  userId?: User['id'] | string;
  isAccepted?: boolean;
  isDeclined?: boolean;
  isExpired?: boolean;
};

export type InvitationListQueryParams =
  | InvitationListQueryParamsFromUser
  | InvitationListQueryParamsFromAccount;

export type InvitationListQueryReturnTypeFromUser = Omit<Invitation, 'user'>[];

export type InvitationListQueryReturnTypeFromAccount = Omit<Invitation, 'account'>[];

export type InvitationListQueryReturnType =
  | InvitationListQueryReturnTypeFromUser
  | InvitationListQueryReturnTypeFromAccount;

export type InvitationJustAccepted = Invitation & { newMembership: Membership };

export class InvitationService {
  async create({
    email,
    name,
    role,
    accountId,
    invitedById,
  }: {
    email: string;
    name: string;
    role: Role;
    accountId: Account['id'];
    invitedById: User['id'];
  }): Promise<Invitation> {
    const obj = await apiRequest('POST', '/api/invitations', {
      json: {
        email,
        name,
        role,
        account: accountId,
        invitedBy: invitedById,
      },
    });

    return obj as Invitation;
  }

  async list({
    params,
  }: {
    params: InvitationListQueryParamsFromUser;
  }): Promise<InvitationListQueryReturnTypeFromUser>;
  async list({
    params,
  }: {
    params: InvitationListQueryParamsFromAccount;
  }): Promise<InvitationListQueryReturnTypeFromAccount>;

  async list({ params }: { params: InvitationListQueryParams }) {
    const paramsStr = getQueryParamsString(params);

    const objs = await apiRequest('GET', `/api/invitations?${paramsStr}`, {});

    if (params?.accountId == null) {
      return objs as InvitationListQueryReturnTypeFromUser;
    }
    return objs as InvitationListQueryReturnTypeFromAccount;
  }

  async get(id: Invitation['id']): Promise<Invitation> {
    const obj = await apiRequest('GET', `/api/invitations/${id}`, {});

    return obj as Invitation;
  }

  async update(id: Invitation['id'], data: { role?: Role; name?: string }): Promise<Invitation> {
    const obj = await apiRequest('PATCH', `/api/invitations/${id}`, {
      json: data,
    });

    return obj as Invitation;
  }

  async delete(id: Invitation['id']) {
    await apiRequest('DELETE', `/api/invitations/${id}`);
  }

  async resend(id: Invitation['id']): Promise<Invitation> {
    const response = await apiRequest('POST', `/api/invitations/${id}/resend`);

    return response as Invitation;
  }

  async accept(id: Invitation['id']): Promise<InvitationJustAccepted> {
    const response = (await apiRequest(
      'POST',
      `/api/invitations/${id}/accept`,
    )) as InvitationJustAccepted;

    store.set(membershipsAtom, 'add', response.newMembership);

    return response;
  }
}

const invitationService = new InvitationService();

export default invitationService;
