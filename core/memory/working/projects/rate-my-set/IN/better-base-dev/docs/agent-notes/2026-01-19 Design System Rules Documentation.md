# Design System Rules Documentation

## Context

- **Date**: 2026-01-19
- **Branch**: `feature--initial-ai-guardrails`
- **Commit at start**: `72a9358`

## Summary

Created comprehensive design system rules documentation at
`.cursor/rules/design-system-rules.mdc` to facilitate Figma-to-code translation and
maintain consistency across the frontend codebase.

## What Was Added

### New File: `.cursor/rules/design-system-rules.mdc`

A comprehensive guide covering:

1. **Design System Overview**
   - Tech stack (Chakra UI v3, React 19, Vite 8, Tanstack Router/Query)
   - Project structure for theme and components

2. **Token Definitions**
   - Base colors and color palettes (purple, gray/neutral, green, red, yellow, blue)
   - Semantic color tokens for backgrounds, foregrounds, text, borders
   - Primary/danger/warning/success/info semantic palettes
   - Typography tokens (fonts, sizes, weights, text styles)
   - Spacing, border radius, and shadow tokens

3. **Component Library**
   - Import sources (native Chakra vs project wrappers)
   - Component recipes (button variants, menu styles)
   - Common patterns (Dialog, Toast, Tooltip, Menu)

4. **Icon System**
   - Phosphor Icons as primary library
   - Heroicons and React Icons as alternatives
   - Usage patterns with Chakra Icon component

5. **Styling Approach**
   - Style props (preferred method)
   - CSS prop for complex nested styles
   - Responsive design patterns
   - Color mode handling

6. **Critical Rules**
   - DOs: Use semantic tokens, text styles, HStack/VStack, gap, compound components
   - DON'Ts: No hardcoded colors, no deprecated v2 patterns, no sx prop

7. **Figma to Code Mapping**
   - Color mapping table
   - Typography mapping table
   - Spacing conversion (4px grid to Chakra tokens)
   - Border radius mapping

8. **Development Commands**
   - Common bun commands for development

## Why This Matters

This documentation enables:

- Faster Figma-to-code translation with clear token mappings
- Consistent styling across the codebase
- Proper use of Chakra UI v3 patterns
- Easier onboarding for new developers and AI agents

## Related Files

- `.cursor/rules/chakra-ui-rules.mdc` - Chakra v3 migration rules
- `AGENTS.md` - Project guidelines (references this new file)
- `frontend/theme/*` - Theme token definitions
- `frontend/components/ui/*` - Component wrappers
