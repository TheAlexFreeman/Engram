import { lazy } from 'react';

// Thanks to https://tanstack.com/router/latest/docs/framework/react/devtools#only-importing-and-using-devtools-in-development
const TanStackRouterDevtools =
  process.env.NODE_ENV === 'production'
    ? () => null // Render nothing in production.
    : lazy(() =>
        // Lazy load in development.
        import('@tanstack/react-router-devtools').then((res) => ({
          default: res.TanStackRouterDevtools,
          // For Embedded Mode
          // default: res.TanStackRouterDevtoolsPanel
        })),
      );

export default TanStackRouterDevtools;
