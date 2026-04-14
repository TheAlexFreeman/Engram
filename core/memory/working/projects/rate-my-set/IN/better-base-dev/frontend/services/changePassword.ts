import { setCsrfToken } from '@/api/csrf';
import { apiRequest } from '@/api/request';
import { InitialData } from '@/api/types/initialData';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

export class ChangePasswordService {
  async changePassword({
    previousPassword,
    newPassword,
    newPasswordConfirm,
  }: {
    previousPassword: string;
    newPassword: string;
    newPasswordConfirm: string;
  }): Promise<InitialData> {
    const responseData = (await apiRequest('POST', `/api/auth/change-password`, {
      json: { previousPassword, newPassword, newPasswordConfirm },
    })) as InitialData;

    setCsrfToken(responseData.csrfToken);
    store.set(initialDataAtom, responseData, {});
    return responseData;
  }
}

const changePasswordService = new ChangePasswordService();
export default changePasswordService;
