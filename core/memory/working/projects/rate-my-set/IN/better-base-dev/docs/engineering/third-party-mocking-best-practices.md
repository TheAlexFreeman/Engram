# Third-Party Mocking Best Practices

## Purpose

Document the repository-level approach for thoroughly testing third-party integrations
without depending on live remote systems.

## Scope

This document covers testing patterns for:

- HTTP API clients
- SDK-backed remote systems
- storage-style APIs such as S3-compatible listings
- syncs, crawlers, and other workflows that consume those boundaries

## Navigation

- For client-boundary guidance, go to
  [API Client Best Practices](./api-client-best-practices.md).
- For client-boundary examples, go to
  [API Client Reference Patterns](./api-client-reference-patterns.md).
- For sync strategy guidance, go to
  [Sync Best Practices](./sync-best-practices.md).
- For concrete sync examples, go to
  [Sync Reference Patterns](./sync-reference-patterns.md).
- For concrete third-party mock-system examples, go to
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md).

## Start Here Checklist

When setting up a third-party test harness, check these first:

- block real network calls by default
- mock at one explicit client or SDK boundary
- test the boundary directly and the higher-level workflow separately
- prefer a reusable stateful mock system over scattered one-off stubs when the source is
  non-trivial
- control time and caches explicitly when auth or expiration behavior matters

## Core Goals

- keep tests deterministic and fast
- make it hard to accidentally hit real remote systems
- keep the third-party boundary explicit and easy to mock
- test both the boundary itself and the higher-level workflows that consume it
- simulate enough real remote behavior that failures are meaningful

## Start With One Explicit Boundary

Thorough mocking gets much easier when the code has one obvious remote boundary.

That boundary might be:

- a dedicated HTTP client class
- a configured SDK-client accessor
- a thin fetcher module

Tests should usually mock at that boundary or just below it.

## Block Real Network Calls By Default

Prefer repo-wide fixtures that prevent accidental outbound traffic unless a test
explicitly configures it.

That usually means:

- `requests_mock` autouse fixtures for `requests`
- `respx_mock` autouse fixtures for `httpx`
- explicit patching for SDK constructors such as `boto3.client(...)`

## Test Two Layers Separately

The cleanest pattern is to test two related but distinct layers:

- direct client or fetch-boundary tests
- higher-level sync, crawl, or workflow tests that consume that boundary

Direct boundary tests should focus on:

- auth behavior
- request shaping
- pagination behavior
- response parsing
- caching and expiration logic
- error classification and error-message safety

Higher-level workflow tests should focus on:

- insert, update, noop, and delete behavior
- orchestration across batches or pages
- checkpoint and timestamp behavior
- database effects
- counters and state transitions

## Prefer Dedicated Mock Systems Over Scattered Stubs

For non-trivial integrations, prefer a reusable mock system class instead of scattered
one-off response stubs.

A good mock system usually has:

- one class responsible for registering mock routes or fake SDK behavior
- internal state maps that represent remote records
- helper methods such as `create`, `retrieve`, `list`, `update`, and `delete`
- explicit parsing of request path, query params, and body where relevant
- explicit errors when a test hits an unsupported request shape

## Pair Mock Systems With Makers Or Factories

For sync-heavy integrations, the strongest pattern is often:

- one reusable mock remote system
- one or more maker or factory helpers that create realistic remote records
- optional helpers that also materialize corresponding local records

This keeps remote and local test data aligned and reduces repeated hand-authored payloads.

## Use Structured Fixtures

Prefer a small fixture surface that sets up the full collaboration landscape for a test.

Useful patterns include:

- autouse setup fixtures on test classes for `respx_mock`, `time_machine`, `settings`,
  `mocker`, and log capture
- one integration fixture that returns a structure object, for example `api + maker`
- setup helpers that clear caches and reset singleton state before each test

## Control Time, Caches, And Auth Explicitly

Third-party integrations often hide subtle state in:

- token caches
- cookie caches
- retry timers
- TTL caches
- timestamp-based refresh logic

When testing those paths:

- freeze or control time explicitly
- clear caches before each test
- patch cache timers if a library uses a clock source that the time-freezing tool does
  not patch
- assert both the cached and refreshed paths

## Mock At The SDK Boundary For SDK-Backed Sources

When a mature SDK already is the client boundary, do not over-wrap it just for tests.

Patch the SDK constructor or accessor and return a fake object that implements the
methods the production code actually uses.

If production code depends on paginator behavior, the fake should expose a paginator, not
just one flattened list.

## Assert More Than Return Values

Strong integration tests should assert:

- which outbound endpoint or SDK method was used
- auth or credential inputs
- cache behavior across time shifts
- request bodies or params when shaping matters
- safe error strings versus verbose debug strings when secrets must not leak
- database write shape when sparse updates or deletes matter

## Prefer Explicit Missing-Mock Failures

If a test hits an endpoint or SDK call the mock system does not support yet, fail loudly.

Do not silently swallow the call or return permissive placeholder data.

If a future reader only remembers one thing from this document, it should be:

- make the fake behave enough like the real boundary that unsupported behavior fails
  loudly and meaningful behavior stays testable

## Generic Pseudocode: Stateful HTTP Mock System

```python
class MockThirdPartyApi:
    def __init__(self, respx_mock, settings) -> None:
        self.respx_mock = respx_mock
        self.settings = settings
        self.records_by_id = {}

    def setup_mocking(self) -> None:
        self.respx_mock.post(self.auth_url).mock(side_effect=self._auth)
        self.respx_mock.get(url__regex=self.detail_regex).mock(
            side_effect=self._retrieve_one
        )
        self.respx_mock.get(self.list_url).mock(side_effect=self._list)
        self.respx_mock.post(self.list_url).mock(side_effect=self._create)
        self.respx_mock.put(url__regex=self.detail_regex).mock(
            side_effect=self._update
        )

    def _create(self, request):
        body = parse_request_json(request)
        record = {"id": make_id(), **body}
        self.records_by_id[record["id"]] = record
        return Response(201, json=record)

    def _retrieve_one(self, request, record_id):
        return Response(200, json=self.records_by_id[record_id])

    def _update(self, request, record_id):
        body = parse_request_json(request)
        self.records_by_id[record_id].update(body)
        return Response(200, json=self.records_by_id[record_id])

    def _list(self, request):
        return Response(200, json={"results": list(self.records_by_id.values())})
```

## Generic Pseudocode: SDK Client Patch With Paginator

```python
@define()
class PatchRemoteClientResult:
    mock: MagicMock
    get_client: Callable[[], MockRemoteClient | None]


def patch_remote_client(mocker, *, records, records_per_page=1000):
    fake_client = None

    def build_client(*, endpoint_url, access_key, secret_key, **kwargs):
        nonlocal fake_client
        fake_client = MockRemoteClient(
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            records=records,
            records_per_page=records_per_page,
        )
        return fake_client

    mock = mocker.patch("path.to.module.sdk")
    mock.client.side_effect = build_client
    return PatchRemoteClientResult(mock=mock, get_client=lambda: fake_client)


class MockRemoteClient:
    def get_paginator(self, endpoint_name):
        assert endpoint_name == "list_objects_v2"

        class MockPaginator:
            def paginate(self, *, Bucket, Prefix):
                for batch in batches_in_deterministic_order():
                    yield {
                        "Contents": batch,
                        "IsTruncated": has_more(batch),
                        "NextContinuationToken": next_token(batch),
                    }

        return MockPaginator()
```

## Related Docs

- Generic client-boundary guidance:
  [API Client Best Practices](./api-client-best-practices.md)
- Concrete client-boundary examples:
  [API Client Reference Patterns](./api-client-reference-patterns.md)
- Generic sync guidance:
  [Sync Best Practices](./sync-best-practices.md)
- Concrete sync examples:
  [Sync Reference Patterns](./sync-reference-patterns.md)
- Concrete third-party mocking examples:
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md)
