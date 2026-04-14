import { apiRequest } from '@/api/request';
import { type CheckUserDeleteResult, type User } from '@/api/types/accounts/users';
import { AuthenticatedUser } from '@/api/types/auth/users';
import { userAtom } from '@/state/auth';
import store from '@/state/store';

export interface UserUpdatePayload {
  name?: string;
}

export class UserService {
  async update(id: User['id'], payload: UserUpdatePayload): Promise<User> {
    const obj = (await apiRequest('PATCH', `/api/users/${id}`, {
      json: payload,
    })) as User;

    store.set(userAtom, obj);

    return obj;
  }

  async updateUploadedProfileImage(id: User['id'], pi: File) {
    const body = new FormData();
    body.append('uploadedProfileImage', pi);
    const obj = (await apiRequest('POST', `/api/users/${id}/update-uploaded-profile-image`, {
      body,
      responseJson: true,
      isFileUpload: true,
    })) as User;

    store.set(userAtom, obj);

    return obj;
  }

  async deleteUploadedProfileImage(id: User['id']) {
    const updatedUser = await apiRequest('POST', `/api/users/${id}/delete-uploaded-profile-image`, {
      responseJson: true,
    });

    store.set(userAtom, updatedUser as AuthenticatedUser);

    return updatedUser as User;
  }

  async checkDelete(id: User['id']): Promise<CheckUserDeleteResult> {
    const responseData = await apiRequest('POST', `/api/users/${id}/check-delete`, {
      responseJson: true,
    });

    return responseData as CheckUserDeleteResult;
  }

  async delete(id: User['id']) {
    const responseData = await apiRequest('DELETE', `/api/users/${id}`);
    return responseData;
  }
}

const userService = new UserService();

export default userService;
