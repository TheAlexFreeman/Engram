---
source: external-research
origin_session: unknown
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - chakra-ui-3-overview.md
  - react-hook-form-zod.md
  - chakra-ui-3-react-frontend-patterns.md
  - vite-react-build.md
---

# React 19 overview and upgrade notes

React 19 became stable on December 5, 2024, and the React docs are currently on the 19.2 line (published October 1, 2025). The biggest practical shifts are first-class async mutation flows (`Actions`, `useActionState`, `useFormStatus`, `useOptimistic`), the new `use` API for reading promises or context during render, better asset and metadata handling in React DOM, and a cleanup pass on long-deprecated APIs. For an app already on modern React 18 tooling, the upgrade is mostly about removing old escape hatches and adopting the newer form/data primitives where they simplify code.

## Current status

- React 19 is the stable major release.
- React 19.2 is the current documented minor release as of 2026-03-18.
- React 19.2 adds more post-19.0 features on top of the base release, including `<Activity />`, `useEffectEvent`, `cacheSignal`, React Performance Tracks, and partial pre-rendering.

## The important React 19 additions

### 1. Actions and form-native async mutations

React 19's most important ergonomic improvement is the "Actions" model for async updates.

- `useActionState` wraps an async action and gives you the last result plus a pending flag.
- `<form action={fn}>` can call an async function directly instead of requiring a manual submit handler.
- `useFormStatus` lets nested form components read the parent form's pending state without prop drilling.
- `useOptimistic` gives a built-in optimistic UI path for pending mutations.

This materially reduces boilerplate for CRUD-style React apps. A lot of "pending/error/result/reset" logic that previously lived in ad hoc local state can now stay close to the form and the mutation itself.

### 2. `use` for reading promises and context in render

React 19 adds `use` so a component can suspend on a promise directly during render, and it can also read context conditionally. The important boundary is that React warns if the promise is created in render inside a Client Component; the intended model is to pass a promise from a Suspense-aware framework, cache layer, or library.

Practical meaning:

- Strong fit for framework-driven data loading and Server Components.
- Less useful as a raw client-side fetch primitive unless your stack already caches promises correctly.

### 3. React DOM now handles more document and asset work itself

React 19 adds native support for a set of concerns that previously pushed teams toward helper libraries or hand-managed head/asset orchestration:

- document metadata tags like `<title>`, `<meta>`, and `<link>` can be rendered in component trees and React hoists them into `<head>`
- stylesheets can be rendered alongside the components that need them, with `precedence` controlling ordering
- async scripts are deduplicated and can be declared where they are used
- resource hint APIs such as `prefetchDNS`, `preconnect`, `preload`, and `preinit` are available from `react-dom`
- static prerender APIs (`react-dom/static`) improve static HTML generation by waiting for data

This is especially relevant for SSR/framework work, but even plain React apps benefit from cleaner ownership of metadata and third-party script loading.

### 4. Smaller API surface and more consistent refs/context

React 19 continues the long cleanup of legacy APIs:

- function components can receive `ref` as a prop, reducing the need for `forwardRef`
- `<Context>` can be rendered directly as a provider instead of `<Context.Provider>`
- several long-deprecated APIs were removed

The direction is clear: fewer special cases, fewer legacy escape hatches, and more alignment between function components and modern JSX.

## Upgrade path and breaking changes

The official recommendation is:

1. Upgrade to `react@18.3` first.
2. Fix the warnings it surfaces.
3. Ensure the modern JSX transform is enabled.
4. Run the React 19 codemods.
5. Then move to React 19.

Useful official codemods:

- `npx codemod@latest react/19/migration-recipe`
- `npx types-react-codemod@latest preset-19 ./path-to-app`

Important upgrade hazards:

- The new JSX transform is required in React 19.
- Function-component `propTypes` checks are removed, and `defaultProps` for function components are removed in favor of default parameters.
- Legacy context (`contextTypes` / `getChildContext`) is removed.
- String refs are removed.
- `ReactDOM.render`, `ReactDOM.hydrate`, `unmountComponentAtNode`, and `findDOMNode` are removed in favor of the `createRoot` / `hydrateRoot` APIs and normal refs.
- UMD builds are gone; script-tag usage should move to an ESM-based CDN.
- Error handling changed: render-time errors are not re-thrown the same way, and root options now expose `onUncaughtError` / `onCaughtError`.

## TypeScript-specific changes

The TypeScript surface changed enough that it is worth treating as part of the upgrade rather than as cleanup:

- `useRef` now requires an argument.
- all refs are now mutable through a single `RefObject` shape
- ref callback cleanup semantics mean implicit ref callback returns may need to be rewritten
- `ReactElement["props"]` defaults to `unknown` instead of `any`
- the global `JSX` namespace has moved toward `React.JSX`
- `useReducer` typing is improved, but some old explicit generic patterns change

For TS-heavy codebases, the `types-react-codemod` step is not optional busywork; it is the fastest path to a clean migration.

## React 19.2 additions worth knowing

React 19.2 is not a new major, but it does add real features:

- `<Activity />` for keeping parts of the tree hidden but still prerendered
- `useEffectEvent` for event-like logic triggered from effects without over-widening effect dependencies
- `cacheSignal` for Server Component cache lifetimes
- React Performance Tracks in Chrome DevTools
- partial pre-rendering and more SSR APIs in Node environments

For day-to-day product code, `useEffectEvent` is the main one to care about immediately. It gives a cleaner answer to the long-standing "effect depends on too much because callback logic needs fresh props/state" problem.

## Adoption notes for a modern React frontend

For an app already using React 18 with a bundler, strict TypeScript, and idiomatic hooks:

- The upgrade is mostly a tooling and deprecation pass, not a rewrite.
- The fastest user-visible win is usually form/mutation code that can be simplified with Actions and `useOptimistic`.
- The highest migration risk is old ecosystem code still touching removed DOM APIs or React internals.
- If the app depends on custom SSR/framework glue, validate React Server Component and server-action assumptions carefully. React says Server Components are stable for apps, but the underlying framework/bundler integration APIs can still break across React 19.x minors.

## Sources

- React 19 release: https://react.dev/blog/2024/12/05/react-19
- React 19 upgrade guide: https://react.dev/blog/2024/04/25/react-19-upgrade-guide
- React 19.2: https://react.dev/blog/2025/10/01/react-19-2
- `useActionState`: https://react.dev/reference/react/useActionState
- `useOptimistic`: https://react.dev/reference/react/useOptimistic
- `use`: https://react.dev/reference/react/use

Last updated: 2026-03-18
