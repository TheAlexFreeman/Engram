---
source: external-research
origin_session: manual
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
---

# Celery Canvas in depth

Celery Canvas is the part of Celery that turns isolated tasks into workflows. The practical distinction is: `chain` passes results forward through sequential steps, `group` fans work out in parallel, and `chord` waits for a group to finish before running a callback. The sharp edges are mostly about result-backend requirements, unintended argument injection, and error semantics once a workflow is no longer a single task.

## The building block is the signature

Canvas primitives are built from signatures: task invocations captured as serializable objects instead of executed immediately.

```python
from proj.tasks import add

s1 = add.s(2, 2)
s2 = add.si(2, 2)  # immutable signature
```

Useful mental model:

- `.s(...)` creates a normal signature that may receive upstream results
- `.si(...)` creates an immutable signature that will not accept injected positional results
- `.delay(...)` executes immediately and returns `AsyncResult`
- `.apply_async(...)` executes with options like countdown, ETA, routing, or headers

If a step should behave like a fixed callback with its own arguments, prefer `si()` so upstream results do not silently become an extra first argument.

## `chain`: linear pipelines with result passing

`chain` links signatures left-to-right. Each task's return value becomes the first positional argument to the next task unless the next signature is immutable.

```python
from celery import chain

workflow = chain(
    fetch_order.s(order_id),
    normalize_order.s(),
    persist_order.si(),  # do not inject normalized payload here
)

result = workflow.apply_async()
```

High-value behaviors:

- `chain(a.s(), b.s(), c.s())` is equivalent to `a.s() | b.s() | c.s()`
- failures stop downstream execution unless you explicitly recover elsewhere
- the final `AsyncResult` represents the tail task, but parents remain navigable through result metadata
- partial chains are composable: you can define reusable sub-pipelines and append more steps later

Use `link_error` when you need failure-side handling:

```python
sig = chain(
    import_payload.s(batch_id),
    transform_payload.s(),
    store_payload.s(),
)
sig.link_error(report_import_failure.s(batch_id))
sig.apply_async()
```

Keep the error callback idempotent. In Canvas flows, the failure path may itself run after retries or after some side effects have already happened upstream.

## `group`: fan-out parallel work

`group` dispatches a collection of signatures in parallel and returns a `GroupResult`.

```python
from celery import group

job = group(fetch_remote_record.s(pk) for pk in record_ids)
group_result = job.apply_async()
values = group_result.get()
```

`GroupResult` is the operational handle for the whole batch. It lets you inspect readiness, join results, revoke unfinished tasks, or restore prior grouped execution from backend state.

Important caveats from Celery's docs:

- groups are not "real tasks"; they are signatures that expand into many independent tasks
- linked callbacks/errbacks are passed through to member tasks, so they may run once per failing child, not once for the group as a whole
- because errbacks can run multiple times, they must tolerate repeated invocation

That means `group(...).link(error_handler.s())` is usually the wrong abstraction if you want one aggregate failure handler. Reach for a `chord` instead.

## `chord`: fan-out, then fan-in

A `chord` is a `group` header plus a body callback that runs only after all header tasks finish successfully.

```python
from celery import chord

workflow = chord(
    fetch_remote_record.s(pk) for pk in record_ids
)(aggregate_records.s(batch_id))
```

The callback receives the header results as its first argument:

```python
@shared_task
def aggregate_records(results: list[dict], batch_id: int) -> None:
    ...
```

Operationally, chords are where result backends start to matter:

- tasks inside a chord must not ignore results
- chords are unsupported with the RPC result backend
- Celery uses backend-specific machinery to detect header completion before releasing the body
- Redis, Memcached, and DynamoDB increment a counter after each header task; other backends periodically unlock via a polling task

This is why chords feel more fragile than chains: they depend on correct backend/result configuration, not just broker delivery.

## Redis and reliability implications for chords

For a Redis-backed stack, the main consequence is simple: chords are viable, but only if you treat result storage as part of workflow correctness rather than optional observability.

Practical implications:

- keep results enabled for chord-participating tasks even if most other tasks use `ignore_result=True`
- make the body idempotent because callback release is a higher-stakes coordination step
- expect failure handling to be split between failing header tasks and the chord body's own error path
- avoid huge chord headers unless you understand the memory and backend-pressure implications

For Alex's stack, a good default is: use Redis-backed chords for moderate fan-out/fan-in workflows, but keep the aggregation callback narrow and durable.

## `chunks` and `starmap`: bulk-dispatch helpers

Canvas also includes higher-level bulk helpers:

- `task.starmap(iterable)` calls one task many times with tuple-unpacked arguments
- `task.map(iterable)` calls one task many times with a single argument each
- `task.chunks(iterable, n)` splits a long input iterable into chunked task messages

Example:

```python
from proj.tasks import process_row

header = process_row.chunks(rows, 100)
header.apply_async()
```

Use these when the bottleneck is message overhead rather than task logic. `chunks` is especially useful when a million tiny tasks would overwhelm the broker or result backend.

## Composition patterns that work well

The safest compositions are the ones where each boundary has a clear contract.

### Fan-out pipeline, then aggregate

```python
from celery import chord

workflow = chord(
    parse_document.s(doc_id) for doc_id in document_ids
)(build_search_index.s(index_id))
```

Good fit:

- many independent upstream tasks
- one deterministic reducer
- callback can be retried safely

### Group inside a chain

```python
from celery import chain, group

workflow = chain(
    prepare_batch.s(batch_id),
    group(run_model.s(item_id) for item_id in item_ids),
    summarize_batch.s(batch_id),
)
```

This is useful when the fan-out stage is only one step in a larger pipeline. The summary step receives the group outputs.

### Chain inside a group

```python
from celery import group

workflow = group(
    fetch_user.s(user_id) | enrich_user.s() | persist_user.s()
    for user_id in user_ids
)
```

This is often easier to reason about than one enormous nested chord: each lane is a self-contained pipeline.

## Composition patterns that break

The common failures are conceptual, not syntactic.

- waiting synchronously inside a task with `.get()` or `.join()` can deadlock worker pools and wastes concurrency
- using mutable signatures where a callback should be fixed can inject unexpected upstream results
- attaching one errback to a `group` and expecting it to run once is incorrect; group errbacks can run multiple times
- making every nested step store large result payloads can turn the backend into the bottleneck
- combining non-idempotent side effects with retries across groups/chords makes partial completion hard to reason about

When a workflow becomes hard to describe in one sentence, split it into smaller task contracts or persist intermediate state in Postgres and launch the next phase explicitly.

## Error handling and partial completion

Canvas does not make distributed failure atomic. It gives you orchestration primitives, not transactions.

What that means in practice:

- in a `chain`, prior tasks may already have committed side effects when a later task fails
- in a `group`, some tasks may succeed while others fail; you need a policy for partial success
- in a `chord`, the callback does not run unless the header completes successfully, so failed header tasks can strand already-computed partial work

Design rules that age well:

- idempotent tasks by default
- pass identifiers, then re-read authoritative DB state
- persist workflow state transitions explicitly for long-running pipelines
- make compensation steps explicit instead of assuming automatic rollback

## Real-world patterns for this stack

### Parallel API calls, then aggregate

Use a `chord` when Django needs to collect N remote calls and then write one consolidated result.

- header tasks: fetch vendor/API responses independently
- body task: validate aggregate completeness, normalize, and persist

### Multi-step data transformation

Use a `chain` when each step meaningfully depends on the previous result.

- ingest raw payload
- normalize schema
- validate domain constraints
- persist domain object
- enqueue follow-up notifications

### High-volume row processing

Use `chunks` when importing or backfilling many rows.

- chunk primary keys into bounded units
- process each chunk in one task
- optionally follow with a chord body that records batch completion

## Decision guide

- use `chain` for sequential stateful pipelines
- use `group` for parallel independent tasks where aggregation is optional or handled elsewhere
- use `chord` for true fan-out/fan-in workflows where a final reducer depends on all upstream results
- use `si()` whenever callback argument injection would be a bug
- use `chunks` when task-message volume would otherwise dominate

## Related files

- [celery-advanced-patterns.md](celery-advanced-patterns.md)
- [django-production-stack.md](django-production-stack.md)

## Sources

- Celery Canvas guide: https://docs.celeryq.dev/en/stable/userguide/canvas.html
- Celery tasks guide: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- Celery calling guide: https://docs.celeryq.dev/en/stable/userguide/calling.html

Last updated: 2026-03-18
