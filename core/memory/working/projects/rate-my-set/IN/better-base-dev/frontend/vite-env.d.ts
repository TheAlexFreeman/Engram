/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Environment
  readonly VITE_ENVIRONMENT: 'dev' | 'test' | 'ci' | 'stage' | 'prod';

  // Sentry
  readonly VITE_SENTRY_IS_ENABLED: 'true' | 'false';
  // NOTE: The auth token should only be available in `vite.config.ts`.
  readonly VITE_SENTRY_AUTH_TOKEN: string;
  readonly VITE_SENTRY_DSN: string;
  readonly VITE_SENTRY_ORG: string;
  readonly VITE_SENTRY_PROJECT: string;
  readonly VITE_SENTRY_RELEASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
