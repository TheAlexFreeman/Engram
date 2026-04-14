import { defineConfig, normalizePath } from 'vite';

import babel from '@rolldown/plugin-babel';
import { sentryVitePlugin } from '@sentry/vite-plugin';
import { tanstackRouter } from '@tanstack/router-plugin/vite';
// * Future Upgrade (React Compiler non-babel): Move back to `import react from
//   '@vitejs/plugin-react-swc'` if/once React Compiler supports `swc` and/or `vite +
//   swc`, etc.
import react from '@vitejs/plugin-react';
import path from 'path';
import { viteStaticCopy } from 'vite-plugin-static-copy';

const frontendBabelIncludePattern = /[\\/]frontend[\\/].*\.[jt]sx?$/;

const ReactCompilerConfig = {
  target: '19',
};

// Debug: Log Sentry env vars during build (can uncomment if ever needing to debug this
// again).
// console.log('[vite.config] Sentry env vars check:', {
//   VITE_SENTRY_IS_ENABLED: process.env.VITE_SENTRY_IS_ENABLED,
//   VITE_SENTRY_AUTH_TOKEN: process.env.VITE_SENTRY_AUTH_TOKEN ? '[SET]' : '[NOT SET]',
//   VITE_SENTRY_ORG: process.env.VITE_SENTRY_ORG,
//   VITE_SENTRY_PROJECT: process.env.VITE_SENTRY_PROJECT,
//   VITE_SENTRY_RELEASE: process.env.VITE_SENTRY_RELEASE,
// });

const isSentryEnabled = !!(
  process.env.VITE_SENTRY_IS_ENABLED === 'true' &&
  process.env.VITE_SENTRY_AUTH_TOKEN &&
  process.env.VITE_SENTRY_ORG &&
  process.env.VITE_SENTRY_PROJECT &&
  process.env.VITE_SENTRY_RELEASE
);

// Debug: Log `isSentryEnabled` during build (can uncomment if ever needing to debug
// this again).
// console.log('[vite.config] isSentryEnabled:', isSentryEnabled);

// https://vitejs.dev/config/
export default defineConfig({
  // NOTE: See https://github.com/MrBin99/django-vite#vitejs for the background on why a
  // number of these values are set to what they are.

  // NOTE: This should match `settings.STATIC_URL` from the Django settings.
  base: '/static/bundler/',
  build: {
    // At the time of writing, choosing to set this to 2MB.
    chunkSizeWarningLimit: 2000, // 2MB
    // NOTE: We set this to `false` because we have `python manage.py collectstatic`
    // handle copying the public directory to the static folder in a way that Vite AND
    // Django can both resolve the files with their respective way of accessing the
    // files.
    copyPublicDir: false,
    manifest: 'manifest.json',
    // Path where we want the assets to be compiled.
    outDir: path.resolve(__dirname, './dist'),
    rollupOptions: {
      input: { main: path.resolve(__dirname, './frontend/main.tsx') },
    },
    sourcemap: true,
  },
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
    // `@vitejs/plugin-react` 6 moved custom Babel transforms out of the plugin options,
    // so React Compiler and Jotai transforms now run through Rolldown's Babel plugin.
    babel({
      include: frontendBabelIncludePattern,
      plugins: [
        // https://react.dev/learn/react-compiler#usage-with-vite
        ['babel-plugin-react-compiler', ReactCompilerConfig], // Must run first!
      ],
      // https://jotai.org/docs/tools/devtools#babel-plugin-setup-optional-but-highly-recommended
      // The preset includes two plugins:
      // - `jotai/babel/plugin-react-refresh` to enable hot reload for atoms.
      // - `jotai/babel/plugin-debug-label` to automatically add debug labels to atoms.
      presets: ['jotai/babel/preset'],
      // * Future Upgrade (React Compiler non-babel): Re-enable once React Compiler
      //   supports `swc` and/or `vite + swc`, etc.
      // plugins: [
      //   // https://jotai.org/docs/tools/swc#swc-jotai-debug-label
      //   ['@swc-jotai/debug-label', {}],
      //   // https://jotai.org/docs/tools/swc#swc-jotai-react-refresh
      //   ['@swc-jotai/react-refresh', {}],
      // ],
    }),
    viteStaticCopy({
      targets: [
        {
          src: normalizePath(
            path.resolve(__dirname, './node_modules/jsoneditor/dist/jsoneditor.css'),
          ),
          dest: path.resolve(__dirname, './backend/static/js/jsoneditor'),
        },
        {
          src: normalizePath(
            path.resolve(__dirname, './node_modules/jsoneditor/dist/jsoneditor.js'),
          ),
          dest: path.resolve(__dirname, './backend/static/js/jsoneditor'),
        },
        {
          src: normalizePath(
            path.resolve(__dirname, './node_modules/jsoneditor/dist/jsoneditor.map'),
          ),
          dest: path.resolve(__dirname, './backend/static/js/jsoneditor'),
        },
        {
          src: normalizePath(
            path.resolve(__dirname, './node_modules/jsoneditor/dist/jsoneditor.min.css'),
          ),
          dest: path.resolve(__dirname, './backend/static/js/jsoneditor'),
        },
        {
          src: normalizePath(
            path.resolve(__dirname, './node_modules/jsoneditor/dist/jsoneditor.min.js'),
          ),
          dest: path.resolve(__dirname, './backend/static/js/jsoneditor'),
        },
        {
          src: normalizePath(
            path.resolve(__dirname, './node_modules/jsoneditor/dist/img/jsoneditor-icons.svg'),
          ),
          dest: path.resolve(__dirname, './backend/static/js/jsoneditor/img'),
        },
      ],
    }),
    [
      ...(isSentryEnabled
        ? [
            sentryVitePlugin({
              org: process.env.VITE_SENTRY_ORG,
              project: process.env.VITE_SENTRY_PROJECT,
              authToken: process.env.VITE_SENTRY_AUTH_TOKEN,
              telemetry: false,
              debug: true,
              release: {
                name: process.env.VITE_SENTRY_RELEASE,
              },
              sourcemaps: {
                filesToDeleteAfterUpload: [path.resolve(__dirname, './dist/**/*.map')],
              },
            }),
          ]
        : []),
    ],
  ],
  resolve: {
    // Thanks to https://stackoverflow.com/a/66515600 and
    // https://stackoverflow.com/a/67676242
    alias: { '@': path.resolve(__dirname, './frontend') },
  },
  server: {
    watch:
      process.env.DEV_VITE_FROM_DOCKER === 'true' &&
      (process.env.DEV_VITE_USE_POLLING_IN_DEV_DOCKER === 'true' ||
        process.env.DEV_VITE_USE_POLLING_IN_DEV_DOCKER === 'True')
        ? {
            usePolling: true,
            // NOTE: Default at the time of writing is 100 and 300 respectively for
            // `interval` and `binaryInterval`. Not expecting this to be typically run
            // in Docker at the time of writing, and for that and other reasons, setting
            // these to considerably higher values.
            interval: 1000,
            binaryInterval: 1000,
          }
        : {},
    // This should be the exact path to the Vite server.
    origin: 'http://localhost:4020',
  },
});
