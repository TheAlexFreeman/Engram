import { createRouter } from '@tanstack/react-router';

import DefaultNotFoundComponent from './DefaultNotFoundComponent.tsx';
import queryClient from './queries/client';
import { routeTree } from './routeTree.gen';

const router = createRouter({
  // https://tanstack.com/router/latest/docs/framework/react/guide/router-context
  context: { queryClient },
  // https://tanstack.com/router/latest/docs/framework/react/api/router/RouterOptionsType#defaultnotfoundcomponent-property
  defaultNotFoundComponent: DefaultNotFoundComponent,
  // https://tanstack.com/router/v1/docs/framework/react/guide/preloading#supported-preloading-strategies
  defaultPreload: 'intent',
  // https://tanstack.com/router/v1/docs/framework/react/guide/preloading#preload-delay
  defaultPreloadDelay: 50,
  // https://tanstack.com/router/latest/docs/framework/react/guide/scroll-restoration
  scrollRestoration: true,
  // https://tanstack.com/router/latest/docs/framework/react/guide/data-loading#passing-all-loader-events-to-an-external-cache
  defaultPreloadStaleTime: 0,
  routeTree,
});

export default router;
