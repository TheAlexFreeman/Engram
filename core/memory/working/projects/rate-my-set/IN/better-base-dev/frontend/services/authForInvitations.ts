import { setCsrfToken } from '@/api/csrf';
import { apiRequest } from '@/api/request';
import { Invitation } from '@/api/types/accounts/invitations';
import { User } from '@/api/types/accounts/users';
import { InitialData } from '@/api/types/initialData';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

export class AuthForInvitationsService {
  async loginFromInvitation({
    invitation,
    email,
    password,
  }: {
    invitation: Invitation;
    email: User['email'];
    password: string;
  }): Promise<InitialData> {
    const responseData = (await apiRequest('POST', `/api/auth/login/from-invitation`, {
      json: { invitationId: invitation.id, email, password },
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    store.set(initialDataAtom, responseData, { justLoggedIn: true });

    return responseData;
  }

  async signupFromInvitation(
    {
      invitation,
      email,
      firstName,
      lastName,
      password,
      passwordConfirm,
    }: {
      invitation: Invitation;
      email: User['email'];
      firstName: string;
      lastName: string;
      password: string;
      passwordConfirm: string;
    },
    { initiallyLoggedIn }: { initiallyLoggedIn: boolean },
  ): Promise<[InitialData, { justLoggedIn: boolean; justLoggedOut: boolean }]> {
    const responseData = (await apiRequest('POST', `/api/auth/signup/from-invitation`, {
      json: { invitationId: invitation.id, email, firstName, lastName, password, passwordConfirm },
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    const justLoggedIn = responseData.user.isAuthenticated;
    const justLoggedOut = initiallyLoggedIn && !responseData.user.isAuthenticated;
    store.set(initialDataAtom, responseData, { justLoggedIn, justLoggedOut });

    return [responseData, { justLoggedIn, justLoggedOut }];
  }
}

const authForInvitationsService = new AuthForInvitationsService();

export default authForInvitationsService;
