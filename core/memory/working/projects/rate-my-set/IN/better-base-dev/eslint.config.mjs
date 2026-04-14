import babelParser from '@babel/eslint-parser';
import { fixupConfigRules, fixupPluginRules } from '@eslint/compat';
import { FlatCompat } from '@eslint/eslintrc';
import js from '@eslint/js';
import htmlEslint from '@html-eslint/eslint-plugin';
import parser from '@html-eslint/parser';
import pluginQuery from '@tanstack/eslint-plugin-query';
import pluginRouter from '@tanstack/eslint-plugin-router';
import typescriptEslint from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import oxlint from 'eslint-plugin-oxlint';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import * as espree from 'espree';
import globals from 'globals';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

export default [
  ...pluginQuery.configs['flat/recommended'],
  ...pluginRouter.configs['flat/recommended'],
  reactHooks.configs.flat['recommended-latest'],
  {
    ignores: [
      'README.md',
      'index.html',
      '**/.agents',
      '**/.agents/**',
      '**/.cache',
      '**/.coverage',
      '**/.dmypy.json',
      '**/.git',
      '**/.gitignore',
      '**/.mypy_cache',
      '**/.pytest_cache',
      '**/.react-email',
      '**/.ruff_cache',
      '**/.swc',
      '**/.venv',
      '**/.vscode',
      '**/__pycache__',
      '__pycache__/*',
      '**/build',
      '**/chakra-ejected-example',
      '**/dist',
      '**/dist-ssr',
      '**/docs',
      '**/htmlcov',
      '**/node_modules',
      'node_modules/*',
      'emails/exported',
      'emails/exported/*',
      'openapi/generated/*',
      '**/package-lock.json',
      '**/public',
      'public/*',
      'backend/static/js/jsoneditor',
      'backend/templates',
      'backend/templates/*',
      '**/staticfiles',
      'staticfiles/*',
      '**/routeTree.gen.ts',
      '**/tsconfig.json',
      '**/tsconfig.app.json',
      '**/tsconfig.node.json',
      // AGENTS.md (CLAUDE.md is gitignored and symlinks to this) contains intentional
      // code examples showing both correct and incorrect patterns, which would trigger
      // lint warnings.
      'AGENTS.md',
      'CLAUDE.md',
    ],
  },
  ...fixupConfigRules(
    compat.extends(
      'eslint:recommended',
      'plugin:@typescript-eslint/recommended',
      'plugin:react/recommended',
      'plugin:markdown/recommended-legacy',
      'prettier',
      'plugin:storybook/recommended',
    ),
  ),
  {
    plugins: {
      react: fixupPluginRules(react),
      '@typescript-eslint': fixupPluginRules(typescriptEslint),
      'react-refresh': reactRefresh,
    },

    languageOptions: {
      globals: { ...globals.browser },

      parser: espree,
      ecmaVersion: 'latest',
      sourceType: 'module',
    },

    settings: { react: { version: 'detect' } },

    rules: {
      'no-console': 'warn',
      'react/react-in-jsx-scope': 'off',
      'react-refresh/only-export-components': [
        'warn',
        {
          // Allow TanStack Router's `Route` export alongside components.
          allowExportNames: ['Route'],
          // Allow `export const Foo = ...` for UI component re-exports.
          allowConstantExport: true,
        },
      ],
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx'],

    languageOptions: { parser: tsParser },
  },
  {
    // TanStack Router route files intentionally export `Route` + have non-exported
    // component functions. This pattern is incompatible with react-refresh's "one
    // component per file" assumption, but works correctly with TanStack Router's auto
    // code splitting.
    files: ['**/routes/**/*.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // Chakra UI snippet files export a mix of forwardRef components and constant
    // re-exports. This is the standard pattern for Chakra UI component wrappers.
    files: ['**/components/ui/**/*.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['**/*.js'],

    languageOptions: { parser: babelParser },
  },
  {
    files: ['**/*.html'],
    ignores: ['backend/**/*.html', 'dist/**/*.html', 'dist-ssr/**/*.html'],
    plugins: {
      '@html-eslint': htmlEslint,
    },
    languageOptions: {
      parser: parser,
    },
    rules: {
      '@html-eslint/indent': ['error', 2],
      '@html-eslint/no-extra-spacing-attrs': ['error', { enforceBeforeSelfClose: true }],
      '@html-eslint/require-closing-tags': [
        'error',
        { selfClosing: 'always', selfClosingCustomPatterns: ['-'] },
      ],
    },
  },
  // eslint-plugin-oxlint MUST be last to disable overlapping ESLint rules.
  ...oxlint.buildFromOxlintConfigFile('./.oxlintrc.json'),
];
