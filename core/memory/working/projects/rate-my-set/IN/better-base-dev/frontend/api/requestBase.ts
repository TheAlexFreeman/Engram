import {
  NotAuthenticatedError,
  NotFoundError,
  PermissionsError,
  ServerError,
  ValidationError,
} from './types/api';

export type HttpMethod =
  | 'GET'
  | 'POST'
  | 'PUT'
  | 'PATCH'
  | 'DELETE'
  | 'OPTIONS'
  | 'HEAD'
  | 'CONNECT'
  | 'TRACE';

export type ApiRequestBaseOptions = Partial<RequestInit> & {
  json?: object;
  responseJson?: boolean;
  isFileUpload?: boolean;
  abortSignal?: AbortSignal;
};

type _ApiRequestBaseOptionsWithResponseJsonTrue = ApiRequestBaseOptions & {
  responseJson?: true;
};

type _ApiRequestBaseOptionsWithResponseJsonNotTrue = ApiRequestBaseOptions & {
  responseJson: false;
};

export async function apiRequestBase(
  method: HttpMethod,
  path: string,
  options?: _ApiRequestBaseOptionsWithResponseJsonTrue,
): Promise<object>;

export async function apiRequestBase(
  method: HttpMethod,
  path: string,
  options: _ApiRequestBaseOptionsWithResponseJsonNotTrue,
): Promise<Response>;

export async function apiRequestBase(
  method: HttpMethod,
  path: string,
  options?: ApiRequestBaseOptions,
): Promise<object | Response>;

export async function apiRequestBase(
  method: HttpMethod,
  path: string,
  options?: ApiRequestBaseOptions,
) {
  const { responseJson = true, abortSignal, ...rest } = options ?? {};

  const contentTypeKey = 'Content-Type';
  let contentType = ((rest?.headers as Record<string, string>) || {})[contentTypeKey];
  if (!contentType && !responseJson) {
    throw new Error('Content-Type header is required for non-JSON converting responses.');
  } else if (!contentType) {
    contentType = 'application/json';
  }
  if (!rest.headers) {
    rest.headers = {};
  }
  (rest.headers as Record<string, string>)[contentTypeKey] = contentType;

  if (rest.json != null && contentType === 'application/json') {
    rest.body = JSON.stringify(rest.json);
  }

  if (options?.isFileUpload) {
    // This lets the browser set the Content-Type header automatically, which will be
    // automatically correct for the file being uploaded.
    delete (rest.headers as Record<string, string>)[contentTypeKey];
  }

  const response = await fetch(path, {
    method,
    signal: abortSignal,
    ...rest,
  });

  if (response.status === 400) {
    const errorJson = await response.json();
    throw new ValidationError(response, errorJson);
  } else if (response.status === 401) {
    const errorJson = await response.json();
    throw new NotAuthenticatedError(response, errorJson);
  } else if (response.status === 403) {
    const errorJson = await response.json();
    const permissionsError = new PermissionsError(response, errorJson);
    if (permissionsError.isNotAuthenticatedError) {
      throw permissionsError.asNotAuthenticatedError();
    }
    throw permissionsError;
  } else if (response.status === 404) {
    throw new NotFoundError(response);
  } else if (response.status >= 500 && response.status < 600) {
    throw new ServerError(response);
  } else if (response.status >= 400 && response.status < 600) {
    throw new Error(`Unexpected ${response.status} response from server.`);
  }

  if (method === 'DELETE' && response.status === 204) {
    return responseJson ? {} : response;
  } else if (responseJson) {
    const responseData = await response.json();
    return responseData;
  }

  return response;
}
