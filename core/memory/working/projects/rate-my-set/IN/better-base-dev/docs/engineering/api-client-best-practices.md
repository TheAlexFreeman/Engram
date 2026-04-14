# API Client Best Practices

## Purpose

Document the repository-level approach for third-party client or fetch boundaries used
by syncs and related workflows.

## Scope

This document covers the boundary between application code and a third-party read or
write surface.

That boundary might be:

- a dedicated HTTP client class
- a configured SDK-client accessor
- a thin fetcher module for a warehouse-backed remote source

## Navigation

- For sync strategy guidance, go to
  [Sync Best Practices](./sync-best-practices.md).
- For concrete sync examples, go to
  [Sync Reference Patterns](./sync-reference-patterns.md).
- For concrete client examples, go to
  [API Client Reference Patterns](./api-client-reference-patterns.md).
- For third-party testing guidance, go to
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).
- For concrete third-party mock-system examples, go to
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md).

## Start Here Checklist

When designing a new client boundary, check these first:

- pick one obvious client or fetch boundary for the source family
- keep transport concerns in that boundary and keep local sync decisions out of it
- expose a small public surface with clear list, detail, iterate, or write methods
- make pagination, response shaping, and auth behavior owned by the boundary
- make the boundary easy to acquire and easy to test directly

## Why Have A Dedicated Boundary

Sync and workflow code should not be littered with raw transport setup.

One explicit boundary makes it easier to:

- centralize auth and credentials
- centralize base URL, endpoint, or SDK configuration
- centralize timeouts and transport defaults
- expose one obvious public API for list, detail, iterate, or write methods
- mock and test the source cleanly

## What The Client Boundary Should Usually Own

- auth and credential usage
- base URL, endpoint, or connection configuration
- default timeout, SSL/TLS, and low-level request settings
- path normalization and source-specific parameter shaping
- pagination and iteration helpers
- repetitive response-envelope parsing when the source uses one
- easy acquisition from source config, model metadata, or a cached accessor

## What The Client Boundary Should Usually Not Own

- local ORM writes
- insert versus update versus delete decisions
- normalized comparison rules for syncs
- business-specific sync orchestration

Keep transport concerns and local sync decisions separate.

## Public Surface Guidance

Prefer a small public surface with obvious method names.

Typical examples:

- `get_list(...)`
- `get_detail(...)`
- `iterate_all(...)`
- `request(...)`
- one or two source-specific write helpers when the remote API is awkward enough that
  centralizing them clearly helps

Do not create a giant grab bag of poorly related helper methods.

## Construction Guidance

Client acquisition should be easy and obvious.

Useful shapes include:

- `source.client`
- a module-level cached `client`
- a factory such as `get_client_for_company(...)`
- a model-declared `remote_fetcher`
- a cached SDK accessor such as `bucket.s3_client`

The durable rule is:

- the caller should not need to reconstruct transport details inline

## Response Shaping

If the remote source uses repetitive envelope structures, centralize that parsing in the
client boundary.

Examples:

- typed response wrappers
- prepared request argument objects
- one parsed list/detail contract returned to callers

The goal is to make the public client API stable and easy to consume.

## Pagination Guidance

If the source is paginated, make the client boundary own the pagination details.

That includes:

- page or cursor parameters
- continuation tokens
- iteration helpers
- deterministic ordering parameters when the source supports them

Do not spread paging rules across every sync loop.

## SDK-Backed Sources

If a mature SDK already is the client abstraction, do not add a custom wrapper class
without a good reason.

A configured accessor can be enough when it still gives the codebase:

- one obvious place for credentials and config
- one obvious place for endpoint or region setup
- one easy object to patch in tests

The rule is not "always wrap the SDK."
The rule is "always have one obvious client boundary."

## Warehouse-Backed Remote Sources

If the remote data is already mirrored into a warehouse-backed table or ORM model, a
thin fetcher module can legitimately be the client boundary.

That boundary should still own:

- remote ordering
- projection
- chunking
- source-specific filters

## Testing Expectations

The client boundary should be easy to test directly.

That usually means:

- block real network calls by default
- test auth, request shaping, pagination, and error behavior directly
- separately test syncs or workflows that consume the client

If a future reader only remembers one thing from this document, it should be:

- the client boundary is there to keep transport details centralized and easy to test,
  not to hide sync decisions or local persistence behavior

Detailed mocking guidance lives in
[Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).

## Related Docs

- Generic sync patterns:
  [Sync Best Practices](./sync-best-practices.md)
- Concrete sync examples:
  [Sync Reference Patterns](./sync-reference-patterns.md)
- Concrete client examples:
  [API Client Reference Patterns](./api-client-reference-patterns.md)
- Generic third-party mocking guidance:
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md)
- Concrete third-party mocking examples:
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md)
