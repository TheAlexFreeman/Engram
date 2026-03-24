---
source: external-research
origin_session: unknown
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - ../web-fundamentals/html-semantics-accessibility.md
---

# Chakra UI 3 overview

Chakra UI v3 launched on October 22, 2024 as a major rewrite of Chakra's component and styling model. The important shift is that Chakra is no longer just "a prop-based component library" in the v2 sense; it is now a more explicit design-system runtime built around `createSystem`, tokens, recipes, compound components, and Ark UI-powered stateful primitives. For a React developer already comfortable with Chakra v2, v3 is meaningfully more powerful, but it also expects more intentional composition and theme architecture.

## What changed in v3

### Architecture

Chakra describes v3 as a unification of three ideas:

- Ark UI for headless/state-machine-driven component logic
- Panda CSS-inspired theming and styling APIs
- Park UI as a design-system influence for consistent scales and naming

The important nuance is that Chakra did not switch fully to Panda internally. Chakra's own v3 announcement says it still keeps Emotion and runtime CSS-in-JS for now to reduce migration breakage and preserve dynamic styling.

### Component model

The most visible API shift is the move toward compound components and namespaced imports:

- `Accordion.Root`, `Accordion.Item`, `Accordion.ItemTrigger`
- `List.Root`, `List.Item`
- `Card.Root`, `Card.Header`, `Card.Body`

This makes structure more explicit and reduces flat import noise. Chakra's comparison guide also frames this as a move toward cleaner imports and more maintainable composition.

### State machines and accessibility

Chakra v3 now uses Ark UI as the foundation for logic-heavy components. The stated goal is more stable behavior and consistency across components like menus, popovers, and other interactive primitives. For teams building dense product UIs, this is one of the more important under-the-hood upgrades because it improves the reliability of focus management, disclosure state, and keyboard interactions.

### Performance and styling engine changes

The migration guide calls out three big performance-facing changes:

- improved reconciliation performance by `4x`
- improved re-render performance by `1.6x`
- an externalized styling engine that sits outside the React tree

Chakra also replaced the old `framer-motion` dependency with platform CSS animations and leaned into CSS cascade layers for more predictable overrides.

## What changed from Chakra v2

The migration surface is real. The main changes are not cosmetic.

- Theme setup moved from `extendTheme(...)` to `defineConfig(...)` + `createSystem(...)`
- `ChakraProvider` now takes a `value` prop containing the system instead of a `theme` prop
- `styleConfig` and `multiStyleConfig` were replaced by `recipes` and `slotRecipes`
- many components moved to compound-component APIs
- boolean props generally dropped the `is` prefix, for example `isDisabled` became `disabled`
- some older prop names moved closer to modern CSS, for example `Stack spacing` became `gap`
- nested styling moved to the `css` prop with explicit `&` selectors

The migration guide recommends starting with the codemod:

- `npx @chakra-ui/codemod upgrade`

It also requires Node 20.x and tells v2 projects to uninstall `@emotion/styled` and `framer-motion`.

## Ecosystem changes

Chakra v3 intentionally removed some bundled opinions:

- `@chakra-ui/icons` is gone; Chakra recommends `react-icons` or `lucide-react`
- built-in color-mode management moved to `next-themes`
- the old hooks package was largely removed in favor of dedicated hook libraries
- `@chakra-ui/next-js` is gone; `asChild` is the preferred integration path for framework components

This makes Chakra smaller and more focused, but it also means v3 expects you to treat the surrounding React ecosystem as part of your stack instead of expecting Chakra to provide every utility itself.

## Color mode in v3

One easy mistake is assuming Chakra still manages color mode the v2 way. The migration guide says the core package removed `ColorModeProvider`, `useColorMode`, `useColorModeValue`, `LightMode`, `DarkMode`, and `ColorModeScript` in favor of `next-themes`.

The docs do still provide a color-mode snippet that recreates a familiar API on top of `next-themes`, so the developer experience can still feel Chakra-like. The important point is architectural: color mode is no longer a core Chakra runtime concern.

## Why Chakra 3 matters for React frontends

Chakra 3 is a stronger fit than Chakra 2 when you care about:

- building a real design system rather than a pile of component overrides
- keeping accessibility defaults while still owning markup structure
- scaling variants and multi-part components without theme-function sprawl
- combining product UI needs with a typed token system

The tradeoff is that Chakra 3 asks for more explicit system design. It is less "drop in some components and tweak props forever" and more "define tokens, recipes, and component composition boundaries early."

## Relationship to modern React

Chakra documents support for React Server Components, but it is careful about the boundary:

- Chakra components can be used from server component trees without marking the page itself with `"use client"`
- Chakra hooks and `chakra()` factory-created components do require client boundaries

That makes Chakra workable in modern React/Next.js stacks, but it is still primarily a client-component UI library, not a server-first styling system.

See also:

- [react-19-overview.md](react-19-overview.md)
- [chakra-ui-3-styling-system.md](chakra-ui-3-styling-system.md)
- [chakra-ui-3-react-frontend-patterns.md](chakra-ui-3-react-frontend-patterns.md)

## Sources

- Chakra UI v3 announcement: https://chakra-ui.com/blog/announcing-v3
- Chakra v2 vs v3 comparison: https://chakra-ui.com/blog/chakra-v2-vs-v3-a-detailed-comparison
- Chakra v3 migration guide: https://chakra-ui.com/docs/get-started/migration
- Chakra server components docs: https://chakra-ui.com/docs/components/concepts/server-components
- Chakra composition docs: https://chakra-ui.com/docs/components/concepts/composition

Last updated: 2026-03-18
