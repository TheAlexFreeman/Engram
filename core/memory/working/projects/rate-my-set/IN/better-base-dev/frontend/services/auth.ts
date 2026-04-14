import { setCsrfToken } from '@/api/csrf';
import { apiRequest } from '@/api/request';
import { User } from '@/api/types/accounts/users';
import { InitialData } from '@/api/types/initialData';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

export class AuthService {
  async refreshMe(): Promise<InitialData> {
    const beforeData = store.get(initialDataAtom);
    const beforeAuthenticated = beforeData?.user?.isAuthenticated || false;

    const responseData = (await apiRequest('POST', `/api/auth/refresh-me`)) as InitialData;

    const afterAuthenticated = beforeData?.user?.isAuthenticated || false;
    const justLoggedIn = !beforeAuthenticated && afterAuthenticated;
    const justLoggedOut = beforeAuthenticated && !afterAuthenticated;

    setCsrfToken(responseData.csrfToken);
    store.set(initialDataAtom, responseData, {
      justLoggedIn: justLoggedIn,
      justLoggedOut: justLoggedOut,
    });

    return responseData;
  }

  async login({
    email,
    password,
  }: {
    email: User['email'];
    password: string;
  }): Promise<InitialData> {
    const responseData = (await apiRequest('POST', `/api/auth/login`, {
      json: { email, password },
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    store.set(initialDataAtom, responseData, { justLoggedIn: true });

    return responseData;
  }

  async logout(): Promise<InitialData> {
    const responseData = (await apiRequest('POST', `/api/auth/logout`, {
      json: {},
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    store.set(initialDataAtom, responseData, { justLoggedOut: true });

    return responseData;
  }

  async signup(
    {
      email,
      firstName,
      lastName,
      password,
      passwordConfirm,
    }: {
      email: User['email'];
      firstName: string;
      lastName: string;
      password: string;
      passwordConfirm: string;
    },
    { initiallyLoggedIn }: { initiallyLoggedIn: boolean },
  ): Promise<[InitialData, { justLoggedIn: boolean; justLoggedOut: boolean }]> {
    const responseData = (await apiRequest('POST', `/api/auth/signup`, {
      json: { email, firstName, lastName, password, passwordConfirm },
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    const justLoggedIn = responseData.user.isAuthenticated;
    const justLoggedOut = initiallyLoggedIn && !responseData.user.isAuthenticated;
    store.set(initialDataAtom, responseData, { justLoggedIn, justLoggedOut });

    return [responseData, { justLoggedIn, justLoggedOut }];
  }

  async signupResendVerificationEmail({ email }: { email: User['email'] }): Promise<InitialData> {
    const responseData = (await apiRequest('POST', `/api/auth/signup/resend-verification-email`, {
      json: { email },
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    store.set(initialDataAtom, responseData, {});

    return responseData;
  }
}

const authService = new AuthService();

export default authService;
