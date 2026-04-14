import React from 'react';

import {
  captureConsoleIntegration,
  replayIntegration,
  init as sentryInit,
  tanstackRouterBrowserTracingIntegration,
} from '@sentry/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { RouterProvider } from '@tanstack/react-router';
import { Provider } from 'jotai';
import ReactDOM from 'react-dom/client';

import { Provider as ChakraProvider } from '@/components/ui/provider';
import '@fontsource/public-sans/300.css';
import '@fontsource/public-sans/400.css';
import '@fontsource/public-sans/500.css';
import '@fontsource/public-sans/600.css';
import '@fontsource/public-sans/700.css';
import Toaster from './components/ui/toaster/toaster-display.tsx';
import JotaiDevTools from './devtools/jotaiDevtools.tsx';
import queryClient from './queries/client.ts';
import router from './router.tsx';
import store from './state/store.ts';
import { system } from './theme';

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

const _sentryDsn = import.meta.env.VITE_SENTRY_DSN || '';
sentryInit({
  dsn: _sentryDsn,
  release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
  enabled: !!(
    import.meta.env.PROD &&
    import.meta.env.VITE_SENTRY_IS_ENABLED === 'true' &&
    _sentryDsn &&
    // NOTE: Using `11` as a rather arbitrary length to make sure there's at least
    // something there.
    _sentryDsn.length > 11
  ),
  integrations: [
    tanstackRouterBrowserTracingIntegration(router),
    captureConsoleIntegration({
      levels: ['warn', 'error'],
    }),
    replayIntegration({
      maskAllText: false,
      blockAllMedia: false,
    }),
  ],
  tracesSampleRate: 0.05,
  replaysSessionSampleRate: 0.05,
  replaysOnErrorSampleRate: 0.2,
});

const rootElement = document.getElementById('root')!;
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <Provider store={store}>
        <JotaiDevTools store={store} />
        <ChakraProvider value={system}>
          <QueryClientProvider client={queryClient}>
            <ReactQueryDevtools initialIsOpen={false} />
            <RouterProvider router={router} />
            <Toaster />
          </QueryClientProvider>
        </ChakraProvider>
      </Provider>
    </React.StrictMode>,
  );
}
