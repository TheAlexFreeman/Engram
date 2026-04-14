import { getInitialServerData } from './initialServerData';
import { apiRequestBase } from './requestBase';
import { CsrfToken } from './types/auth/csrf';

const _csrfContainer: { csrfToken: CsrfToken } = { csrfToken: '' };

export type GetCsrfTokenOptions = {
  forceRefresh?: boolean;
};

export const getCsrfToken = async (options?: GetCsrfTokenOptions) => {
  const force = options?.forceRefresh;

  if (!_csrfContainer.csrfToken) {
    const initialData = getInitialServerData();
    if (initialData.csrfToken) {
      _csrfContainer.csrfToken = initialData.csrfToken;
    }
  }

  if (!_csrfContainer.csrfToken || force) {
    const latest = await _getCsrfTokenFromAPI();
    _csrfContainer.csrfToken = latest;
  }

  return _csrfContainer.csrfToken;
};

export const setCsrfToken = (csrfToken: CsrfToken) => {
  if (csrfToken) {
    _csrfContainer.csrfToken = csrfToken;
  }
};

const _getCsrfTokenFromAPI = async (): Promise<CsrfToken> => {
  const data = await apiRequestBase('POST', '/api/auth/csrf');
  return (data as { csrfToken: CsrfToken }).csrfToken;
};
