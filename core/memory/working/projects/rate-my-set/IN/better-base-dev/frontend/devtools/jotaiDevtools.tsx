import { lazy } from 'react';

// https://github.com/jotaijs/jotai-devtools?tab=readme-ov-file#with-provider
if (process.env.NODE_ENV !== 'production') {
  void import('jotai-devtools/styles.css');
}

const JotaiDevTools =
  process.env.NODE_ENV === 'production'
    ? () => null // Render nothing in production.
    : lazy(() =>
        // Lazy load in development.
        import('jotai-devtools').then((res) => ({
          default: res.DevTools,
        })),
      );

export default JotaiDevTools;
