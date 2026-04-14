import { apiRequest } from '@/api/request';
import { ChangeEmailRequest } from '@/api/types/auth/changeEmail';

export class ChangeEmailService {
  async retrieve(): Promise<ChangeEmailRequest> {
    const responseData = await apiRequest('GET', `/api/auth/change-email/retrieve`, {});

    return responseData as ChangeEmailRequest;
  }

  async request(data: { toEmail: string }): Promise<ChangeEmailRequest> {
    const responseData = await apiRequest('POST', `/api/auth/change-email/request`, {
      json: data,
    });

    return responseData as ChangeEmailRequest;
  }

  async resend(): Promise<ChangeEmailRequest> {
    const responseData = await apiRequest('POST', `/api/auth/change-email/resend`);

    return responseData as ChangeEmailRequest;
  }
}

const changeEmailService = new ChangeEmailService();

export default changeEmailService;
