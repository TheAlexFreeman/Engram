import { QueryClient } from '@tanstack/react-query';

import { defaultRetry } from './defaults';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: defaultRetry,
    },
  },
});

export default queryClient;
