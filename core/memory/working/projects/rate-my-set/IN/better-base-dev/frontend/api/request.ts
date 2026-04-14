import { getCsrfToken } from './csrf';
import { apiRequestBase, type ApiRequestBaseOptions, type HttpMethod } from './requestBase';
import { PermissionsError } from './types/api';

export type { ApiRequestBaseOptions, HttpMethod } from './requestBase';

export type ApiRequestOptions = ApiRequestBaseOptions & {
  requireCsrf?: boolean;
  csrfAction?: 'shouldRefresh';
};

type _ApiRequestOptionsWithResponseJsonTrue = ApiRequestOptions & {
  responseJson?: true;
};

type _ApiRequestOptionsWithResponseJsonNotTrue = ApiRequestOptions & {
  responseJson: false;
};

export async function apiRequest(
  method: HttpMethod,
  path: string,
  options?: _ApiRequestOptionsWithResponseJsonTrue,
): Promise<object>;

export async function apiRequest(
  method: HttpMethod,
  path: string,
  options: _ApiRequestOptionsWithResponseJsonNotTrue,
): Promise<Response>;

export async function apiRequest(
  method: HttpMethod,
  path: string,
  options?: ApiRequestOptions,
): Promise<object | Response>;

export async function apiRequest(method: HttpMethod, path: string, options?: ApiRequestOptions) {
  const { requireCsrf = true, csrfAction, ...rest } = options ?? {};
  const requestOptions: ApiRequestBaseOptions = { ...rest };

  if (requireCsrf) {
    const csrfToken = await getCsrfToken({ forceRefresh: csrfAction === 'shouldRefresh' });
    const headers = { ...((requestOptions.headers as Record<string, string>) || {}) };
    headers['X-CSRFToken'] = csrfToken;
    requestOptions.headers = headers;
  }

  try {
    return await apiRequestBase(method, path, requestOptions);
  } catch (error) {
    if (
      requireCsrf &&
      csrfAction !== 'shouldRefresh' &&
      error instanceof PermissionsError &&
      error.isCSRFError
    ) {
      return await apiRequest(method, path, { ...(options ?? {}), csrfAction: 'shouldRefresh' });
    }
    throw error;
  }
}
